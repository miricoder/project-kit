"""Filing service: auth, limits, retries and error codes, with the model stubbed."""
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from dumpit_ops import Context, decide
from service.app import create_app
from service.limits import Limits
from service.model import ModelOutputError, ModelReply, ProviderError

NOW = datetime(2026, 2, 23, 9, 0, tzinfo=timezone.utc)


class StubModel:
    name = "stub"

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), 0

    def propose(self, request):
        self.calls += 1
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return ModelReply(reply, 1000, 200)


def request_body(text="paid 42 for groceries", **over):
    return {"capture_id": "c1", "text": text, "source": "typed",
            "captured_at": "2026-02-23T09:00:00", "tz": "Europe/Lisbon",
            "currency": "EUR", "context": {}, **over}


GROCERIES = [{"op": "create_expense", "amount_cents": 4200, "date": "2026-02-23",
              "category": "Groceries", "description": "groceries"}]


def setup(*replies, per_install_daily=200, cap_eur=2.0):
    model = StubModel(*replies)
    limits = Limits(per_install_daily=per_install_daily, daily_cap_eur=cap_eur,
                    clock=lambda: NOW)
    client = TestClient(create_app(model=model, limits=limits,
                                   eur_per_mtok_in=0.10, eur_per_mtok_out=0.50))
    token = client.post("/v1/install").json()["install_token"]
    return client, {"Authorization": f"Bearer {token}"}, model, limits


def test_install_issues_a_token_and_keeps_only_its_hash():
    client, headers, _, limits = setup(GROCERIES)
    token = headers["Authorization"].split()[1]
    stored = [row[0] for row in limits.db.execute("SELECT token_hash FROM install")]
    assert token not in stored and len(stored) == 1 and len(stored[0]) == 64


def test_a_capture_is_filed():
    client, headers, model, _ = setup(GROCERIES)
    response = client.post("/v1/file", json=request_body(), headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["ops"] == GROCERIES and body["capture_id"] == "c1"
    assert body["prompt_version"] == "p1" and body["model"] == "stub"
    assert body["usage"] == {"input_tokens": 1000, "output_tokens": 200}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer nope"},
                                     {"Authorization": "Basic abc"}])
def test_an_unknown_token_is_refused(headers):
    client, _, model, _ = setup(GROCERIES)
    assert client.post("/v1/file", json=request_body(), headers=headers).status_code == 401
    assert model.calls == 0


def test_a_malformed_request_is_400():
    client, headers, _, _ = setup(GROCERIES)
    assert client.post("/v1/file", content=b"{", headers=headers).status_code == 400
    bad = request_body(source="email")
    assert client.post("/v1/file", json=bad, headers=headers).status_code == 400


def test_text_over_4000_characters_is_413():
    client, headers, model, _ = setup(GROCERIES)
    ok = client.post("/v1/file", json=request_body("x" * 4000), headers=headers)
    assert ok.status_code == 200
    over = client.post("/v1/file", json=request_body("x" * 4001), headers=headers)
    assert over.status_code == 413 and model.calls == 1


def test_the_per_install_daily_limit_is_429_with_retry_after():
    client, headers, model, _ = setup(GROCERIES, per_install_daily=2)
    for _ in range(2):
        assert client.post("/v1/file", json=request_body(), headers=headers).status_code == 200
    limited = client.post("/v1/file", json=request_body(), headers=headers)
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) == 15 * 3600     # 09:00 UTC to midnight
    assert model.calls == 2


def test_the_global_spend_cap_is_503():
    # 1000 in + 200 out at 0.10/0.50 per Mtok = 200 micro-euros per call
    client, headers, model, _ = setup(GROCERIES, cap_eur=0.0004)
    for _ in range(2):
        assert client.post("/v1/file", json=request_body(), headers=headers).status_code == 200
    assert client.post("/v1/file", json=request_body(), headers=headers).status_code == 503
    assert model.calls == 2


def test_output_that_breaks_the_schema_is_retried_once():
    client, headers, model, _ = setup([{"op": "launch"}], GROCERIES)
    response = client.post("/v1/file", json=request_body(), headers=headers)
    assert response.status_code == 200 and response.json()["ops"] == GROCERIES
    assert model.calls == 2


@pytest.mark.parametrize("bad", [[{"op": "launch"}], ModelOutputError("not JSON")])
def test_output_that_breaks_the_schema_twice_is_502(bad):
    client, headers, model, _ = setup(bad)
    response = client.post("/v1/file", json=request_body(), headers=headers)
    assert response.status_code == 502 and model.calls == 2
    assert "ops" not in response.json()


def test_a_provider_failure_is_503():
    client, headers, _, _ = setup(ProviderError("down"))
    assert client.post("/v1/file", json=request_body(), headers=headers).status_code == 503


def test_health_names_the_prompt_and_model():
    client, _, _, _ = setup(GROCERIES)
    assert client.get("/v1/health").json() == {"status": "ok", "prompt_version": "p1",
                                               "model": "stub"}


def test_logs_never_carry_the_capture(caplog):
    client, headers, _, _ = setup(GROCERIES)
    with caplog.at_level("INFO", logger="dumpit.service"):
        client.post("/v1/file", json=request_body("paid 42 for groceries at Lidl"),
                    headers=headers)
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "Lidl" not in logged and "4200" not in logged and '"create_expense": 1' in logged


# Scenario: implausible amount is not filed as an expense (service + phone-side Validator)
def test_implausible_amount_from_the_service_ends_as_a_note():
    implausible = [{"op": "create_expense", "amount_cents": 420_000_000,
                    "date": "2026-02-23", "category": "Eating out", "description": "coffee"}]
    client, headers, _, _ = setup(implausible)
    body = client.post("/v1/file", json=request_body("paid 4200000 for coffee"),
                       headers=headers).json()
    ops, _ = decide("paid 4200000 for coffee", body["ops"], source="typed",
                    today=date(2026, 2, 23), context=Context())
    assert [op["op"] for op in ops] == ["note"]
