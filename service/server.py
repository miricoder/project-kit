"""The Dumpit service: sign-in, sessions, the Captures API, the change feed, and the web app.

    DUMPIT_DATABASE_URL=postgresql://... DUMPIT_ALLOWED_EMAIL=you@example.com \\
        uvicorn service.server:app

docs/spec.md "Interfaces". Every call except sign-in needs the session cookie; calls that
change state also need the X-Dumpit-CSRF header matching the dumpit_csrf cookie. Every query
is scoped by the signed-in user. Captures from one user are filed one at a time (a row lock
on the user), so two devices capturing at once never lose an item.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, ValidationError

from dumpit_ops import Context, decide

from . import db, store
from .filing import ProviderUnavailable, SchemaFailure, propose
from .mailer import ConsoleMailer, Mailer, SmtpMailer
from .model import PROMPT_VERSION, Model

log = logging.getLogger("dumpit.server")

MAX_TEXT = 4000
LINK_MINUTES = 15
LINKS_PER_HOUR = 5
SESSION_COOKIE, CSRF_COOKIE, CSRF_HEADER = "dumpit_session", "dumpit_csrf", "x-dumpit-csrf"
SESSION_DAYS = 400
WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class CaptureIn(BaseModel):
    capture_id: uuid.UUID
    text: str
    source: Literal["typed", "paste"] = "typed"
    captured_at: str
    tz: str


class LinkIn(BaseModel):
    email: str


class TzIn(BaseModel):
    tz: str


def _error(status: int, message: str, headers: Optional[Dict[str, str]] = None) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status, headers=headers)


def _device_label(user_agent: str) -> str:
    ua = user_agent or ""
    device = "iPhone" if "iPhone" in ua else "iPad" if "iPad" in ua else \
        "Android phone" if "Android" in ua else "Mac" if "Macintosh" in ua else \
        "Windows PC" if "Windows" in ua else "Linux computer" if "Linux" in ua else "Device"
    browser = "Safari" if "Safari" in ua and "Chrome" not in ua else "Chrome" if "Chrome" in ua \
        else "Firefox" if "Firefox" in ua else ""
    return f"{device} · {browser}" if browser else device


def _captured_day(captured_at: str) -> date:
    return date.fromisoformat(captured_at[:10])


def create_server(database_url: str, *, model: Optional[Model] = None,
                  mailer: Optional[Mailer] = None, allowed_emails: Optional[List[str]] = None,
                  public_url: Optional[str] = None, dev: bool = False,
                  per_user_daily: int = 200, daily_cap_eur: float = 2.0,
                  eur_per_mtok_in: float = 0.10, eur_per_mtok_out: float = 0.50,
                  clock=time.time, web_dist: Optional[Path] = WEB_DIST) -> FastAPI:
    app = FastAPI(title="Dumpit")
    allowed = {e.strip().lower() for e in (allowed_emails or []) if e.strip()}
    app.state.mailer = mailer or ConsoleMailer()
    app.state.model = model
    version = db.migrate(database_url)

    def conn():
        return db.connect(database_url)

    def now() -> datetime:
        return datetime.fromtimestamp(clock(), tz=timezone.utc)

    def current_model() -> Model:
        if app.state.model is None:
            from .model import AnthropicModel
            app.state.model = AnthropicModel()
        return app.state.model

    # ----------------------------------------------------------------- auth helpers

    def signed_in(request: Request, c) -> Optional[Dict[str, Any]]:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            return None
        row = c.execute(
            "SELECT s.id AS session_id, u.* FROM session s JOIN app_user u ON u.id = s.user_id "
            "WHERE s.token_hash = %s AND s.revoked_at IS NULL", (token_hash(token),)).fetchone()
        if row:
            c.execute("UPDATE session SET last_seen_at = %s WHERE id = %s",
                      (now(), row["session_id"]))
        return row

    def csrf_ok(request: Request) -> bool:
        cookie, header = request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)
        return bool(cookie) and secrets.compare_digest(cookie, header or "")

    def secure(request: Request) -> bool:
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        return proto == "https"

    def base_url(request: Request) -> str:
        if public_url:
            return public_url.rstrip("/")
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host", request.headers.get("host", ""))
        return f"{proto}://{host}"

    def guard(request: Request, c, write: bool = False):
        user = signed_in(request, c)
        if user is None:
            return None, _error(401, "not signed in")
        if write and not csrf_ok(request):
            return None, _error(403, "missing or wrong CSRF header")
        return user, None

    # ----------------------------------------------------------------- health

    @app.get("/v1/health")
    def health() -> Dict[str, Any]:
        name = app.state.model.name if app.state.model else \
            os.environ.get("DUMPIT_MODEL", "claude-haiku-5-5")
        return {"status": "ok", "prompt_version": PROMPT_VERSION, "model": name,
                "schema_version": version, "dev": dev}

    # ----------------------------------------------------------------- sign-in

    @app.post("/v1/auth/link", status_code=202)
    async def auth_link(request: Request) -> Response:
        try:
            body = LinkIn.model_validate(json.loads(await request.body()))
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError):
            return _error(400, "malformed request")
        email = body.email.strip().lower()
        accepted = Response(status_code=202)
        if email not in allowed or not re.fullmatch(r"[^@\s]+@[^@\s]+", email):
            return accepted                     # same answer, no email (allowlist of one)
        with conn() as c:
            recent = c.execute(
                "SELECT count(*) AS n FROM sign_in_link WHERE user_email = %s "
                "AND created_at > %s - interval '1 hour'", (email, now())).fetchone()["n"]
            if recent >= LINKS_PER_HOUR:
                return accepted
            token = secrets.token_urlsafe(32)
            c.execute("INSERT INTO sign_in_link (token_hash, user_email, expires_at, created_at) "
                      "VALUES (%s, %s, %s + make_interval(mins => %s), %s)",
                      (token_hash(token), email, now(), LINK_MINUTES, now()))
        app.state.mailer.send_link(email, f"{base_url(request)}/v1/auth/callback?t={token}")
        return accepted

    @app.get("/v1/auth/callback")
    def auth_callback(request: Request, t: str = "") -> Response:
        expired = RedirectResponse("/?signin=expired", status_code=303)
        if not t:
            return expired
        with conn() as c:
            link = c.execute(
                "UPDATE sign_in_link SET used_at = %s WHERE token_hash = %s AND used_at IS NULL "
                "AND expires_at > %s RETURNING user_email", (now(), token_hash(t), now())).fetchone()
            if link is None:
                return expired
            user = c.execute(
                "INSERT INTO app_user (email) VALUES (%s) ON CONFLICT (email) "
                "DO UPDATE SET email = EXCLUDED.email RETURNING id", (link["user_email"],)).fetchone()
            session_token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
            c.execute("INSERT INTO session (user_id, token_hash, device_label, created_at, "
                      "last_seen_at) VALUES (%s, %s, %s, %s, %s)",
                      (user["id"], token_hash(session_token),
                       _device_label(request.headers.get("user-agent", "")), now(), now()))
        response = RedirectResponse("/", status_code=303)
        age = SESSION_DAYS * 86400
        response.set_cookie(SESSION_COOKIE, session_token, max_age=age, httponly=True,
                            secure=secure(request), samesite="lax", path="/")
        response.set_cookie(CSRF_COOKIE, csrf, max_age=age, httponly=False,
                            secure=secure(request), samesite="lax", path="/")
        return response

    @app.post("/v1/auth/sign-out", status_code=204)
    def sign_out(request: Request) -> Response:
        with conn() as c:
            user, err = guard(request, c, write=True)
            if err:
                return err
            c.execute("UPDATE session SET revoked_at = %s WHERE id = %s",
                      (now(), user["session_id"]))
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE, path="/")
        response.delete_cookie(CSRF_COOKIE, path="/")
        return response

    @app.get("/v1/sessions")
    def sessions(request: Request) -> Response:
        with conn() as c:
            user, err = guard(request, c)
            if err:
                return err
            rows = c.execute("SELECT id, device_label, created_at, last_seen_at FROM session "
                             "WHERE user_id = %s AND revoked_at IS NULL ORDER BY last_seen_at DESC",
                             (user["id"],)).fetchall()
        return JSONResponse({"sessions": [
            {"id": r["id"], "device": r["device_label"], "created_at": r["created_at"].isoformat(),
             "last_seen_at": r["last_seen_at"].isoformat(),
             "current": r["id"] == user["session_id"]} for r in rows]})

    @app.delete("/v1/sessions/{session_id}", status_code=204)
    def revoke_session(request: Request, session_id: int) -> Response:
        with conn() as c:
            user, err = guard(request, c, write=True)
            if err:
                return err
            done = c.execute("UPDATE session SET revoked_at = %s WHERE id = %s AND user_id = %s "
                             "AND revoked_at IS NULL RETURNING id",
                             (now(), session_id, user["id"])).fetchone()
        return Response(status_code=204) if done else _error(404, "no such device")

    @app.get("/v1/me")
    def me(request: Request) -> Response:
        with conn() as c:
            user, err = guard(request, c)
            if err:
                return err
        return JSONResponse({"email": user["email"], "tz": user["tz"],
                             "monthly_budget_cents": user["monthly_budget_cents"]})

    @app.put("/v1/me/tz", status_code=204)
    async def set_tz(request: Request) -> Response:
        try:
            body = TzIn.model_validate(json.loads(await request.body()))
            ZoneInfo(body.tz)
        except (json.JSONDecodeError, ValidationError, ZoneInfoNotFoundError, ValueError):
            return _error(400, "unknown time zone")
        with conn() as c:
            user, err = guard(request, c, write=True)
            if err:
                return err
            c.execute("UPDATE app_user SET tz = %s WHERE id = %s", (body.tz, user["id"]))
        return Response(status_code=204)

    # ----------------------------------------------------------------- captures

    def file_capture(request_user: Dict[str, Any], body: CaptureIn) -> JSONResponse:
        capture_id = str(body.capture_id)
        with conn() as c:
            with c.transaction():
                user = c.execute("SELECT * FROM app_user WHERE id = %s FOR UPDATE",
                                 (request_user["id"],)).fetchone()
                stored = c.execute("SELECT user_id, response FROM capture WHERE id = %s",
                                   (capture_id,)).fetchone()
                if stored and stored["user_id"] != user["id"]:
                    return _error(409, "capture id already used")
                if stored and stored["response"] is not None:
                    return JSONResponse(stored["response"])          # same answer on a repeat

                today = now().date()
                usage = c.execute(
                    "SELECT captures FROM daily_usage WHERE day = %s AND user_id = %s",
                    (today, user["id"])).fetchone()
                if usage and usage["captures"] >= per_user_daily:
                    midnight = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
                    wait = int(86400 - (now() - midnight).total_seconds())
                    return _error(429, "daily capture limit reached",
                                  {"Retry-After": str(max(wait, 1))})
                spent = c.execute("SELECT micro_eur FROM daily_spend WHERE day = %s",
                                  (today,)).fetchone()
                if spent and spent["micro_eur"] >= daily_cap_eur * 1_000_000:
                    return _error(503, "daily spend cap reached")

                said_on = _captured_day(body.captured_at)
                snapshot = store.context_snapshot(c, user, said_on)
                spend = {"micro": 0}

                def count(tokens_in: int, tokens_out: int) -> None:
                    spend["micro"] += round(tokens_in * eur_per_mtok_in
                                            + tokens_out * eur_per_mtok_out)

                model = current_model()
                try:
                    proposal = propose(model, {"capture_id": capture_id, "text": body.text,
                                               "source": body.source,
                                               "captured_at": body.captured_at, "tz": body.tz,
                                               "context": snapshot}, on_usage=count)
                    error = None
                except ProviderUnavailable:
                    error = _error(503, "model provider unavailable")
                except SchemaFailure:
                    error = _error(502, "model output failed the schema check twice")
                c.execute("INSERT INTO daily_spend (day, micro_eur) VALUES (%s, %s) "
                          "ON CONFLICT (day) DO UPDATE SET micro_eur = daily_spend.micro_eur + "
                          "EXCLUDED.micro_eur", (today, spend["micro"]))
                if error is not None:
                    return error

                ops, _ = decide(body.text, proposal.ops, source=body.source, today=said_on,
                                context=Context.from_snapshot(snapshot))
                if not stored:
                    c.execute("INSERT INTO capture (id, user_id, text, source, captured_at, tz, "
                              "status) VALUES (%s, %s, %s, %s, %s, %s, 'failed')",
                              (capture_id, user["id"], body.text, body.source, body.captured_at,
                               body.tz))
                capture = {"capture_id": capture_id, "text": body.text}
                try:
                    with c.transaction():
                        batch_id, seq, lines, status = store.apply_batch(
                            c, user, capture, ops, today=said_on, model=model.name,
                            prompt_version=PROMPT_VERSION)
                except store.FilingConflict:
                    note = [{"op": "note", "text": body.text, "suggestions": []}]
                    batch_id, seq, lines, status = store.apply_batch(
                        c, user, capture, note, today=said_on, model=model.name,
                        prompt_version=PROMPT_VERSION)
                answer = {"capture_id": capture_id, "status": status, "lines": lines, "seq": seq,
                          "batch_id": batch_id, "model": model.name}
                c.execute("UPDATE capture SET status = %s, filed_batch_id = %s, response = %s "
                          "WHERE id = %s", (status, batch_id, json.dumps(answer), capture_id))
                c.execute("INSERT INTO daily_usage (day, user_id, captures) VALUES (%s, %s, 1) "
                          "ON CONFLICT (day, user_id) DO UPDATE SET "
                          "captures = daily_usage.captures + 1", (today, user["id"]))
        log.info(json.dumps({"user": token_hash(str(user["id"]))[:8], "status": status,
                             "ops": [op["op"] for op in ops], "prompt_version": PROMPT_VERSION}))
        return JSONResponse(answer)

    @app.post("/v1/captures")
    async def captures(request: Request) -> Response:
        with conn() as c:
            user, err = guard(request, c, write=True)
        if err:
            return err
        try:
            raw = json.loads(await request.body())
            if isinstance(raw, dict) and isinstance(raw.get("text"), str) \
                    and len(raw["text"]) > MAX_TEXT:
                return _error(413, f"text is over {MAX_TEXT} characters")
            body = CaptureIn.model_validate(raw)
            _captured_day(body.captured_at)
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, ValueError):
            return _error(400, "malformed request")
        if not body.text.strip():
            return _error(400, "nothing to file")
        return file_capture(user, body)

    @app.post("/v1/captures/{capture_id}/retry")
    def retry(request: Request, capture_id: uuid.UUID) -> Response:
        with conn() as c:
            user, err = guard(request, c, write=True)
            if err:
                return err
            row = c.execute("SELECT * FROM capture WHERE id = %s AND user_id = %s",
                            (str(capture_id), user["id"])).fetchone()
        if row is None:
            return _error(404, "no such capture")
        return file_capture(user, CaptureIn(capture_id=capture_id, text=row["text"],
                                            source=row["source"], captured_at=row["captured_at"],
                                            tz=row["tz"]))

    @app.post("/v1/tasks/{task_id}/done")
    async def task_done(request: Request, task_id: int) -> Response:
        try:
            raw = await request.body()
            done = bool(json.loads(raw).get("done", True)) if raw else True
        except (json.JSONDecodeError, AttributeError):
            return _error(400, "malformed request")
        with conn() as c:
            user, err = guard(request, c, write=True)
            if err:
                return err
            mine = c.execute("SELECT id FROM task WHERE id = %s AND user_id = %s "
                             "AND deleted_at IS NULL", (task_id, user["id"])).fetchone()
            if mine is None:
                return _error(404, "no such task")
            with c.transaction():
                seq = c.execute("UPDATE app_user SET seq = seq + 1 WHERE id = %s RETURNING seq",
                                (user["id"],)).fetchone()["seq"]
                c.execute("UPDATE task SET done_at = CASE WHEN %s THEN coalesce(done_at, now()) "
                          "END, rev = rev + 1, updated_seq = %s WHERE id = %s AND user_id = %s",
                          (done, seq, task_id, user["id"]))
        return JSONResponse({"seq": seq})

    @app.get("/v1/changes")
    def changes(request: Request, since: int = 0) -> Response:
        with conn() as c:
            user, err = guard(request, c)
            if err:
                return err
            return JSONResponse(store.changes(c, user["id"], max(since, 0)))

    if dev:
        @app.get("/v1/dev/last-link")
        def dev_last_link() -> Response:
            """Local runs only: the last sign-in link, so you can sign in without email."""
            last = getattr(app.state.mailer, "last_link", lambda: None)()
            return JSONResponse({"link": last})

    # ----------------------------------------------------------------- the web app

    if web_dist is not None and (web_dist / "index.html").is_file():
        index = web_dist / "index.html"

        @app.get("/{path:path}", include_in_schema=False)
        def web(path: str) -> Response:
            target = (web_dist / path).resolve()
            if path and target.is_file() and web_dist.resolve() in target.parents:
                headers = {"Cache-Control": "no-cache"} if path in ("sw.js", "manifest.webmanifest") \
                    else {"Cache-Control": "public, max-age=31536000, immutable"} \
                    if path.startswith("assets/") else None
                return FileResponse(target, headers=headers)
            if path.startswith("v1/"):
                return _error(404, "not found")
            return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app


def from_env() -> FastAPI:
    url = os.environ.get("DUMPIT_DATABASE_URL")
    if not url:
        raise RuntimeError("set DUMPIT_DATABASE_URL to a Postgres database")
    model = None
    if os.environ.get("DUMPIT_MODEL") == "demo":
        from .demo_model import DemoModel
        model = DemoModel()
    smtp = os.environ.get("DUMPIT_SMTP_URL")
    mailer = SmtpMailer(smtp, os.environ.get("DUMPIT_MAIL_FROM", "dumpit@localhost")) \
        if smtp else ConsoleMailer()
    return create_server(
        url, model=model, mailer=mailer,
        allowed_emails=os.environ.get("DUMPIT_ALLOWED_EMAIL", "").split(","),
        public_url=os.environ.get("DUMPIT_PUBLIC_URL"),
        dev=os.environ.get("DUMPIT_DEV") == "1",
        per_user_daily=int(os.environ.get("DUMPIT_PER_USER_DAILY", "200")),
        daily_cap_eur=float(os.environ.get("DUMPIT_DAILY_CAP_EUR", "2.0")),
        eur_per_mtok_in=float(os.environ.get("DUMPIT_EUR_PER_MTOK_IN", "0.10")),
        eur_per_mtok_out=float(os.environ.get("DUMPIT_EUR_PER_MTOK_OUT", "0.50")))


def __getattr__(name: str):
    if name == "app":          # uvicorn service.server:app, built on first use
        return from_env()
    raise AttributeError(name)
