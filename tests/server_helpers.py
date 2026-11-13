"""Helpers for driving the signed-in service in tests: a scripted model, a clock, and a
signed-in client per device."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from service.mailer import ConsoleMailer
from service.model import ModelReply
from service.server import CSRF_COOKIE, create_server

TODAY = "2026-02-23"
EMAIL = "me@example.com"


class ScriptModel:
    """Answers each capture text with the ops scripted for it; anything else is a note."""
    name = "script"

    def __init__(self, script: Optional[Dict[str, Any]] = None):
        self.script = dict(script or {})
        self.requests: List[Dict[str, Any]] = []
        self.windows: List[tuple] = []          # (start, end) of each call

    def propose(self, request: Dict[str, Any]) -> ModelReply:
        import time
        self.requests.append(request)
        start = time.monotonic()
        answer = self.script.get(request["text"])
        if callable(answer):
            answer = answer(request)
        self.windows.append((start, time.monotonic()))
        if answer is None:
            answer = [{"op": "note", "text": request["text"], "suggestions": []}]
        if isinstance(answer, Exception):
            raise answer
        return ModelReply(answer, 1000, 200)


class Clock:
    def __init__(self, t: float = 1_771_840_800.0):      # 2026-02-23 10:00 UTC
        self.t = t

    def __call__(self) -> float:
        return self.t


def make_server(database_url: str, script=None, emails=(EMAIL,), clock=None, **kw):
    model = kw.pop("model", None) or ScriptModel(script)
    mailer = ConsoleMailer()
    app = create_server(database_url, model=model, mailer=mailer, allowed_emails=list(emails),
                        clock=clock or Clock(), web_dist=None, **kw)
    return app, model, mailer


class Device:
    """One browser: its own cookie jar, signed in through an emailed link."""

    def __init__(self, app, mailer: ConsoleMailer, email: str = EMAIL,
                 user_agent: str = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1"):
        self.client = TestClient(app, headers={"user-agent": user_agent})
        self.mailer, self.email = mailer, email

    def sign_in(self) -> "Device":
        assert self.client.post("/v1/auth/link", json={"email": self.email}).status_code == 202
        link = self.mailer.last_link(self.email)
        token = parse_qs(urlparse(link).query)["t"][0]
        response = self.client.get("/v1/auth/callback", params={"t": token},
                                   follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"] == "/"
        return self

    @property
    def csrf(self) -> Dict[str, str]:
        return {"X-Dumpit-CSRF": self.client.cookies.get(CSRF_COOKIE, "")}

    def capture(self, text: str, capture_id: Optional[str] = None, source: str = "typed",
                captured_at: str = f"{TODAY}T09:00:00"):
        return self.client.post("/v1/captures", headers=self.csrf, json={
            "capture_id": capture_id or str(uuid.uuid4()), "text": text, "source": source,
            "captured_at": captured_at, "tz": "Europe/Lisbon"})

    def changes(self, since: int = 0) -> Dict[str, Any]:
        response = self.client.get("/v1/changes", params={"since": since})
        assert response.status_code == 200, response.text
        return response.json()


def expense(cents: int, category: str, description: str, day: str = TODAY, **extra):
    return {"op": "create_expense", "amount_cents": cents, "date": day, "category": category,
            "description": description, **extra}
