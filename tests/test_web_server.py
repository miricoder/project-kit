"""Slice 4, server side: the service serves the web app, ticks tasks done, and the demo
filer handles the sentences the app's examples use."""
from pathlib import Path

from fastapi.testclient import TestClient

from server_helpers import Clock, Device, make_server
from service.demo_model import DemoModel
from service.mailer import ConsoleMailer
from service.server import create_server


def test_the_web_app_is_served_from_the_same_origin(database_url, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Dumpit</title>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    app = create_server(database_url, mailer=ConsoleMailer(), allowed_emails=[], clock=Clock(),
                        web_dist=dist)
    client = TestClient(app)
    assert "Dumpit" in client.get("/").text
    assert "Dumpit" in client.get("/some/screen").text          # the app routes itself
    assert client.get("/assets/app.js").headers["cache-control"].endswith("immutable")
    assert client.get("/v1/nope").status_code == 404
    assert client.get("/../service/server.py").status_code in (200, 404)
    assert "create_server" not in client.get("/../service/server.py").text


def test_ticking_a_task_done_and_back(database_url):
    app, _, mailer = make_server(database_url, {
        "book the car service": [{"op": "create_task", "title": "Book the car service"}]})
    phone = Device(app, mailer).sign_in()
    phone.capture("book the car service")
    task = phone.changes()["items"][0]
    assert phone.client.post(f"/v1/tasks/{task['id']}/done", json={"done": True},
                             headers=phone.csrf).status_code == 200
    assert phone.changes()["items"][0]["done"] is True
    phone.client.post(f"/v1/tasks/{task['id']}/done", json={"done": False}, headers=phone.csrf)
    assert phone.changes()["items"][0]["done"] is False
    assert phone.client.post("/v1/tasks/99999/done", json={}, headers=phone.csrf).status_code == 404


def test_one_sentence_becomes_two_items(database_url):
    """Scenario: one sentence becomes two items (server side, with the demo filer)"""
    app, _, mailer = make_server(database_url, model=DemoModel())
    phone = Device(app, mailer).sign_in()
    answer = phone.capture("paid 42 for groceries and book the car service").json()
    assert [line["kind"] for line in answer["lines"]] == ["expense", "task"]
    assert all(line["undo"] for line in answer["lines"])


def test_demo_filer_understands_the_examples():
    model = DemoModel()

    def ops(text, context=None):
        return model.propose({"text": text, "captured_at": "2026-02-23T09:00:00",
                              "context": context or {}}).ops

    assert ops("coffee 3.50")[0]["amount_cents"] == 350
    assert ops("paid 42 for groceries")[0]["category"] == "Groceries"
    assert ops("my budget is 1400 a month") == [{"op": "set_monthly_budget", "amount_cents": 140000}]
    assert ops("that was 24 not 42", {"expenses": [{"ref": "e1", "amount_cents": 4200}]}) == \
        [{"op": "update", "ref": "e1", "set": {"amount_cents": 2400}}]
    assert ops("the thing with Marta")[0]["op"] == "note"
