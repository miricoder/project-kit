"""Install tokens, the per-install daily limit and the global daily spend cap.

The server keeps only sha256(token), a per-day capture count and a per-day spend; no capture
text, context or model output is ever stored (docs/spec.md, "Security and privacy").
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS install (token_hash TEXT PRIMARY KEY, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS install_day (token_hash TEXT NOT NULL, day TEXT NOT NULL,
    captures INTEGER NOT NULL, PRIMARY KEY (token_hash, day));
CREATE TABLE IF NOT EXISTS spend_day (day TEXT PRIMARY KEY, micro_eur INTEGER NOT NULL);
"""


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Limits:
    def __init__(self, path: str = ":memory:", per_install_daily: int = 200,
                 daily_cap_eur: float = 2.0, clock: Callable[[], datetime] = utc_now):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript(_SCHEMA)
        self.lock = threading.Lock()
        self.per_install_daily = per_install_daily
        self.daily_cap_micro = round(daily_cap_eur * 1_000_000)
        self.clock = clock

    def _day(self) -> str:
        return self.clock().date().isoformat()

    def seconds_to_reset(self) -> int:
        now = self.clock()
        tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(),
                                    tzinfo=timezone.utc)
        return max(1, int((tomorrow - now).total_seconds()))

    def issue(self) -> str:
        token = secrets.token_urlsafe(32)          # 256 bits
        with self.lock, self.db:
            self.db.execute("INSERT INTO install VALUES (?, ?)",
                            (token_hash(token), self.clock().isoformat()))
        return token

    def known(self, token: Optional[str]) -> bool:
        if not token:
            return False
        with self.lock:
            row = self.db.execute("SELECT 1 FROM install WHERE token_hash = ?",
                                  (token_hash(token),)).fetchone()
        return row is not None

    def take_capture(self, token: str) -> bool:
        """Count one capture against today's limit; False when the limit is reached."""
        key, day = token_hash(token), self._day()
        with self.lock, self.db:
            row = self.db.execute(
                "SELECT captures FROM install_day WHERE token_hash = ? AND day = ?",
                (key, day)).fetchone()
            used = row[0] if row else 0
            if used >= self.per_install_daily:
                return False
            self.db.execute("INSERT OR REPLACE INTO install_day VALUES (?, ?, ?)",
                            (key, day, used + 1))
        return True

    def over_spend_cap(self) -> bool:
        with self.lock:
            row = self.db.execute("SELECT micro_eur FROM spend_day WHERE day = ?",
                                  (self._day(),)).fetchone()
        return (row[0] if row else 0) >= self.daily_cap_micro

    def add_spend(self, micro_eur: int) -> None:
        day = self._day()
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO spend_day VALUES (?, ?) "
                "ON CONFLICT(day) DO UPDATE SET micro_eur = micro_eur + excluded.micro_eur",
                (day, micro_eur))
