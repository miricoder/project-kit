"""Slice 3: sign-in and the server store, against a real Postgres (tests/pg.py)."""
import threading
import time
import uuid
from urllib.parse import parse_qs, urlparse

import psycopg
import pytest

from service import db
from server_helpers import EMAIL, TODAY, Clock, Device, ScriptModel, expense, make_server

GROCERIES = [expense(4200, "Groceries", "Groceries")]


def count(database_url, sql, *args):
    with psycopg.connect(database_url) as c:
        return c.execute(sql, args).fetchone()[0]


# ---- sign-in ---------------------------------------------------------------------------

def test_old_sign_in_link_is_refused(database_url):
    """Scenario: an old sign-in link does not sign anyone in"""
    clock = Clock()
    app, _, mailer = make_server(database_url, clock=clock)
    device = Device(app, mailer)
    device.client.post("/v1/auth/link", json={"email": EMAIL})
    token = parse_qs(urlparse(mailer.last_link()).query)["t"][0]
    clock.t += 16 * 60
    response = device.client.get("/v1/auth/callback", params={"t": token},
                                 follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/?signin=expired"   # the page offers a new link
    assert count(database_url, "SELECT count(*) FROM session") == 0
    assert device.client.get("/v1/me").status_code == 401


def test_a_link_works_once(database_url):
    app, _, mailer = make_server(database_url)
    device = Device(app, mailer).sign_in()
    token = parse_qs(urlparse(mailer.last_link()).query)["t"][0]
    again = Device(app, mailer).client.get("/v1/auth/callback", params={"t": token},
                                          follow_redirects=False)
    assert again.headers["location"] == "/?signin=expired"
    assert count(database_url, "SELECT count(*) FROM session") == 1
    assert device.client.get("/v1/me").json()["email"] == EMAIL


def test_sign_in_link_only_goes_to_the_allowed_email(database_url):
    """Scenario: a sign-in link is only sent to the user's own email"""
    app, _, mailer = make_server(database_url)
    device = Device(app, mailer)
    other = device.client.post("/v1/auth/link", json={"email": "someone@example.com"})
    own = device.client.post("/v1/auth/link", json={"email": EMAIL})
    assert other.status_code == own.status_code == 202
    assert other.content == own.content
    assert [to for to, _ in mailer.sent] == [EMAIL]


def test_sign_in_links_are_rate_limited(database_url):
    app, _, mailer = make_server(database_url)
    client = Device(app, mailer).client
    for _ in range(7):
        assert client.post("/v1/auth/link", json={"email": EMAIL}).status_code == 202
    assert len(mailer.sent) == 5


def test_tokens_are_stored_only_as_hashes(database_url):
    app, _, mailer = make_server(database_url)
    device = Device(app, mailer).sign_in()
    token = parse_qs(urlparse(mailer.last_link()).query)["t"][0]
    session = device.client.cookies.get("dumpit_session")
    with psycopg.connect(database_url) as c:
        stored = [r[0] for r in c.execute("SELECT token_hash FROM sign_in_link UNION ALL "
                                          "SELECT token_hash FROM session")]
    assert token not in stored and session not in stored
    assert all(len(h) == 64 for h in stored)


def test_signing_out_another_device_ends_its_access(database_url):
    """Scenario: signing out a lost device ends its access"""
    app, _, mailer = make_server(database_url)
    phone = Device(app, mailer).sign_in()
    laptop = Device(app, mailer, user_agent="Mozilla/5.0 (Macintosh) Chrome/130").sign_in()
    listed = phone.client.get("/v1/sessions").json()["sessions"]
    assert len(listed) == 2
    other = next(s for s in listed if not s["current"])
    assert other["device"].startswith("Mac")
    assert phone.client.delete(f"/v1/sessions/{other['id']}", headers=phone.csrf).status_code == 204
    assert laptop.client.get("/v1/changes").status_code == 401   # the app shows sign-in
    assert phone.client.get("/v1/changes").status_code == 200


def test_signing_out_this_device(database_url):
    app, _, mailer = make_server(database_url)
    phone = Device(app, mailer).sign_in()
    assert phone.client.post("/v1/auth/sign-out", headers=phone.csrf).status_code == 204
    assert phone.client.get("/v1/me").status_code == 401


def test_writes_need_the_csrf_header(database_url):
    app, _, mailer = make_server(database_url, {"paid 42 for groceries": GROCERIES})
    phone = Device(app, mailer).sign_in()
    response = phone.client.post("/v1/captures", json={
        "capture_id": str(uuid.uuid4()), "text": "paid 42 for groceries", "source": "typed",
        "captured_at": f"{TODAY}T09:00:00", "tz": "Europe/Lisbon"})
    assert response.status_code == 403
    assert count(database_url, "SELECT count(*) FROM expense") == 0


def test_not_signed_in_is_refused(database_url):
    app, _, mailer = make_server(database_url)
    client = Device(app, mailer).client
    assert client.get("/v1/changes").status_code == 401
    assert client.post("/v1/captures", json={}).status_code == 401


# ---- the store -------------------------------------------------------------------------

def test_data_is_visible_only_to_its_user(database_url):
    """Scenario: data is visible only to the signed-in user"""
    app, _, mailer = make_server(database_url, {
        "paid 42 for groceries": GROCERIES,
        "lunch 12": [expense(1200, "Eating out", "Lunch")]},
        emails=(EMAIL, "second@example.com"))
    first = Device(app, mailer).sign_in()
    second = Device(app, mailer, email="second@example.com").sign_in()
    assert first.capture("paid 42 for groceries").status_code == 200
    assert second.capture("lunch 12").status_code == 200
    mine = second.changes()
    assert [i["amount_cents"] for i in mine["items"]] == [1200]
    assert mine["me"]["email"] == "second@example.com"
    first_ids = [i["id"] for i in first.changes()["items"]]
    for item_id in first_ids:
        assert item_id not in [i["id"] for i in mine["items"]]
    # the model only ever sees the signed-in user's own items
    last = app.state.model.requests[-1]
    assert last["context"]["expenses"] == []


def test_two_devices_capturing_at_once_lose_nothing(database_url):
    """Scenario: two devices capturing at once never lose an item"""
    def slow(ops):
        def answer(request):
            time.sleep(0.2)
            return ops
        return answer

    app, _, mailer = make_server(database_url, {
        "coffee 3.50": slow([expense(350, "Eating out", "Coffee")]),
        "lunch 12": slow([expense(1200, "Eating out", "Lunch")])})
    phone = Device(app, mailer).sign_in()
    laptop = Device(app, mailer, user_agent="Mozilla/5.0 (Macintosh) Chrome/130").sign_in()
    results = {}
    threads = [threading.Thread(target=lambda d, t: results.__setitem__(t, d.capture(t)),
                                args=(d, t)) for d, t in ((phone, "coffee 3.50"),
                                                          (laptop, "lunch 12"))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(r.status_code == 200 for r in results.values())
    (a0, a1), (b0, b1) = sorted(app.state.model.windows)
    assert b0 >= a1, "captures from one user must be filed one at a time"
    amounts = sorted(i["amount_cents"] for i in phone.changes()["items"])
    assert amounts == [350, 1200]
    refs = [i["ref"] for i in phone.changes()["items"]]
    assert len(set(refs)) == 2


def test_a_repeated_capture_is_filed_once(database_url):
    app, model, mailer = make_server(database_url, {"paid 42 for groceries": GROCERIES})
    phone = Device(app, mailer).sign_in()
    capture_id = str(uuid.uuid4())
    first = phone.capture("paid 42 for groceries", capture_id).json()
    again = phone.capture("paid 42 for groceries", capture_id).json()
    assert first == again
    assert len(model.requests) == 1
    assert count(database_url, "SELECT count(*) FROM expense") == 1


def test_filed_lines_name_what_was_filed(database_url):
    app, _, mailer = make_server(database_url, {"paid 42 for groceries": GROCERIES})
    phone = Device(app, mailer).sign_in()
    answer = phone.capture("paid 42 for groceries").json()
    assert answer["status"] == "filed"
    assert answer["lines"][0]["text"] == "Expense €42 · Groceries · today"
    assert answer["lines"][0]["undo"] is True
    assert count(database_url, "SELECT count(*) FROM undo_entry") == 1


def test_capture_text_over_the_limit_is_refused(database_url):
    app, model, mailer = make_server(database_url)
    phone = Device(app, mailer).sign_in()
    assert phone.capture("x" * 4001).status_code == 413
    assert model.requests == []


def test_provider_down_is_503_and_nothing_is_stored(database_url):
    from service.model import ProviderError
    app, _, mailer = make_server(database_url, {"coffee 3.50": ProviderError("down")})
    phone = Device(app, mailer).sign_in()
    assert phone.capture("coffee 3.50").status_code == 503
    assert count(database_url, "SELECT count(*) FROM expense") == 0


def test_daily_limit_returns_429_with_retry_after(database_url):
    app, _, mailer = make_server(database_url, {"coffee 3.50": [expense(350, "Eating out", "Coffee")]},
                                 per_user_daily=1)
    phone = Device(app, mailer).sign_in()
    assert phone.capture("coffee 3.50").status_code == 200
    limited = phone.capture("coffee 3.50")
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0


def test_changes_since_returns_only_newer_items_and_deletions(database_url):
    app, _, mailer = make_server(database_url, {
        "coffee 3.50": [expense(350, "Eating out", "Coffee")],
        "delete the coffee": lambda r: [{"op": "delete", "ref": r["context"]["expenses"][0]["ref"]}]})
    phone = Device(app, mailer).sign_in()
    phone.capture("coffee 3.50")
    seq = phone.changes()["seq"]
    assert phone.changes(seq)["items"] == []
    phone.capture("delete the coffee")
    later = phone.changes(seq)
    assert later["items"] == [] and [d["kind"] for d in later["deleted"]] == ["expense"]


def test_a_validator_rejection_becomes_a_note(database_url):
    app, _, mailer = make_server(database_url, {
        "paid 0 for coffee": [expense(0, "Eating out", "Coffee")]})
    phone = Device(app, mailer).sign_in()
    answer = phone.capture("paid 0 for coffee").json()
    assert answer["status"] == "note"
    assert count(database_url, "SELECT count(*) FROM expense") == 0
    assert count(database_url, "SELECT count(*) FROM note") == 1


# ---- schema ----------------------------------------------------------------------------

def test_migrations_are_recorded_and_rerunnable(database_url):
    assert db.migrate(database_url) == 1
    assert db.migrate(database_url) == 1
    assert count(database_url, "SELECT count(*) FROM schema_meta") == 1
