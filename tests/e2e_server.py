"""A disposable Dumpit server for the browser tests (web/e2e) and for trying the app.

    python -m tests.e2e_server [--port 0] [--host 127.0.0.1]

Starts a throwaway Postgres (tests/pg.py), builds the service with the demo filer, dev
sign-in and the built web app (web/dist), and prints one line `READY <url>` when it is
listening. The harness adds POST /__seed for tests only: it inserts rows straight into the
signed-in user's account so a test can start from "the user has 50 expenses".
"""
from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
import threading

import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.dirname(__file__))

import pg  # noqa: E402
from service import db  # noqa: E402
from service.demo_model import DemoModel  # noqa: E402
from service.mailer import ConsoleMailer  # noqa: E402
from service.server import SESSION_COOKIE, create_server, token_hash  # noqa: E402

EMAIL = "me@example.com"
EMAILS = [EMAIL, "second@example.com"] + [f"u{i}@example.com" for i in range(1, 30)]


def build(database_url: str):
    app = create_server(database_url, model=DemoModel(), mailer=ConsoleMailer(),
                        allowed_emails=EMAILS, dev=True)

    @app.post("/__seed")
    async def seed(request: Request):
        body = await request.json()
        token = request.cookies.get(SESSION_COOKIE, "")
        with db.connect(database_url) as c:
            user = c.execute("SELECT u.id FROM session s JOIN app_user u ON u.id = s.user_id "
                             "WHERE s.token_hash = %s AND s.revoked_at IS NULL",
                             (token_hash(token),)).fetchone()
            if not user:
                return JSONResponse({"error": "not signed in"}, status_code=401)
            uid = user["id"]
            seq = c.execute("UPDATE app_user SET seq = seq + 1 WHERE id = %s RETURNING seq",
                            (uid,)).fetchone()["seq"]

            def ref(prefix):
                n = c.execute("UPDATE app_user SET next_ref = next_ref + 1 WHERE id = %s "
                              "RETURNING next_ref - 1 AS n", (uid,)).fetchone()["n"]
                return f"{prefix}{n}"

            for e in body.get("expenses", []):
                c.execute("INSERT INTO expense (user_id, ref, amount_cents, date, category, "
                          "description, updated_seq) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                          (uid, ref("e"), e["amount_cents"], e["date"], e["category"],
                           e["description"], seq))
            for t in body.get("tasks", []):
                c.execute("INSERT INTO task (user_id, ref, title, due_date, updated_seq) "
                          "VALUES (%s, %s, %s, %s, %s)",
                          (uid, ref("t"), t["title"], t.get("due_date"), seq))
            for t in body.get("trips", []):
                c.execute("INSERT INTO trip (user_id, ref, name, start_date, end_date, "
                          "budget_cents, updated_seq) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                          (uid, ref("p"), t["name"], t["start_date"], t["end_date"],
                           t.get("budget_cents"), seq))
            if "monthly_budget_cents" in body:
                c.execute("UPDATE app_user SET monthly_budget_cents = %s WHERE id = %s",
                          (body["monthly_budget_cents"], uid))
        return JSONResponse({"seq": seq})

    return app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    def interrupt(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    admin, stop = pg.start()
    try:
        database_url = pg.fresh_database(admin)
        app = build(database_url)
        port = args.port
        if not port:
            with socket.socket() as s:
                s.bind((args.host, 0))
                port = s.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host=args.host, port=port, log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        while not server.started:
            thread.join(0.05)
            if not thread.is_alive():
                return 1
        shown = "127.0.0.1" if args.host == "0.0.0.0" else args.host
        print(f"READY http://{shown}:{port}", flush=True)
        try:
            thread.join()
        except KeyboardInterrupt:
            server.should_exit = True
            thread.join(5)
    finally:
        stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
