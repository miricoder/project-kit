"""Postgres access and migrations (docs/spec.md, "Data model").

Migrations are the numbered SQL files in service/migrations. Each runs in its own
transaction and records its number in schema_meta; a failure rolls back that file and stops,
leaving the data as it was. v1 migrations are additive only.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

import psycopg
from psycopg.rows import dict_row

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, row_factory=dict_row)


def migration_files() -> List[Path]:
    return sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql"))


def schema_version(conn: psycopg.Connection) -> int:
    exists = conn.execute("SELECT to_regclass('schema_meta') AS t").fetchone()["t"]
    if not exists:
        return 0
    row = conn.execute("SELECT max(schema_version) AS v FROM schema_meta").fetchone()
    return row["v"] or 0


def migrate(url: str) -> int:
    """Apply every migration newer than the database. Returns the resulting version."""
    with connect(url) as conn:
        current = schema_version(conn)
        conn.commit()
        for path in migration_files():
            number = int(re.match(r"(\d+)", path.name).group(1))
            if number <= current:
                continue
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_meta (schema_version) VALUES (%s)", (number,))
            current = number
        return current
