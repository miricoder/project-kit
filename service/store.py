"""The server store: the Filer that applies a validated batch, the context snapshot the
model sees, and the change feed devices sync from (docs/spec.md, "Data model").

Every query is scoped by user_id. Every change bumps the user's `seq` and stamps the rows it
touched with it, so a device asks for "everything with updated_seq > my last_seq".
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import psycopg

KIND_OF_PREFIX = {"t": "task", "e": "expense", "p": "trip"}
PREFIX_OF_KIND = {v: k for k, v in KIND_OF_PREFIX.items()}
TABLE = {"task": "task", "expense": "expense", "trip": "trip"}
FIELDS = {
    "task": ("title", "due_date", "due_time"),
    "expense": ("amount_cents", "date", "category", "description"),
    "trip": ("name", "start_date", "end_date", "budget_cents"),
}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class FilingConflict(Exception):
    """An op names an item that is not there any more (the Validator saw an older state)."""


# --------------------------------------------------------------------------- formatting

def euros(cents: int) -> str:
    whole, rest = divmod(int(cents), 100)
    return f"€{whole:,}" if not rest else f"€{whole:,}.{rest:02d}"


def day_label(value: Optional[str], today: date) -> Optional[str]:
    if not value:
        return None
    day = date.fromisoformat(str(value))
    if day == today:
        return "today"
    if day == today + timedelta(days=1):
        return "tomorrow"
    if day == today - timedelta(days=1):
        return "yesterday"
    label = f"{DAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]}"
    return label if day.year == today.year else f"{label} {day.year}"


def _iso(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


# --------------------------------------------------------------------------- reads

def _item(conn: psycopg.Connection, user_id: int, ref: str) -> Optional[Dict[str, Any]]:
    kind = KIND_OF_PREFIX[ref[0]]
    row = conn.execute(f"SELECT * FROM {TABLE[kind]} WHERE user_id = %s AND ref = %s "
                       "AND deleted_at IS NULL", (user_id, ref)).fetchone()
    return {**row, "kind": kind} if row else None


def context_snapshot(conn: psycopg.Connection, user: Dict[str, Any], today: date) -> Dict[str, Any]:
    """What the model may refer to: open tasks (≤ 50) and the 10 latest done, expenses from
    the last 30 days (≤ 100), trips not ended more than 30 days ago, the monthly budget."""
    uid = user["id"]
    trips = conn.execute(
        "SELECT * FROM trip WHERE user_id = %s AND deleted_at IS NULL AND end_date >= %s "
        "ORDER BY start_date", (uid, today - timedelta(days=30))).fetchall()
    trip_ref = {t["id"]: t["ref"] for t in conn.execute(
        "SELECT id, ref FROM trip WHERE user_id = %s", (uid,)).fetchall()}
    open_tasks = conn.execute(
        "SELECT * FROM task WHERE user_id = %s AND deleted_at IS NULL AND done_at IS NULL "
        "ORDER BY id DESC LIMIT 50", (uid,)).fetchall()
    done_tasks = conn.execute(
        "SELECT * FROM task WHERE user_id = %s AND deleted_at IS NULL AND done_at IS NOT NULL "
        "ORDER BY done_at DESC LIMIT 10", (uid,)).fetchall()
    expenses = conn.execute(
        "SELECT * FROM expense WHERE user_id = %s AND deleted_at IS NULL AND date >= %s "
        "ORDER BY id DESC LIMIT 100", (uid, today - timedelta(days=30))).fetchall()

    def task(t):
        out = {"ref": t["ref"], "title": t["title"], "done": t["done_at"] is not None}
        if t["due_date"]:
            out["due_date"] = t["due_date"].isoformat()
        if t["due_time"]:
            out["due_time"] = t["due_time"]
        return out

    def expense(e):
        out = {"ref": e["ref"], "amount_cents": e["amount_cents"], "date": e["date"].isoformat(),
               "category": e["category"], "description": e["description"]}
        if e["trip_id"]:
            out["trip_ref"] = trip_ref.get(e["trip_id"])
        return out

    snapshot: Dict[str, Any] = {
        "tasks": [task(t) for t in list(reversed(open_tasks)) + done_tasks],
        "expenses": [expense(e) for e in reversed(expenses)],
        "trips": [{"ref": t["ref"], "name": t["name"], "start_date": t["start_date"].isoformat(),
                   "end_date": t["end_date"].isoformat(),
                   **({"budget_cents": t["budget_cents"]} if t["budget_cents"] else {})}
                  for t in trips],
    }
    if user.get("monthly_budget_cents"):
        snapshot["monthly_budget_cents"] = user["monthly_budget_cents"]
    return snapshot


def row_view(kind: str, row: Dict[str, Any], trip_refs: Dict[int, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"kind": kind, "id": row["id"], "ref": row.get("ref"),
                           "updated_seq": row["updated_seq"]}
    if kind == "task":
        out.update(title=row["title"], due_date=_iso(row["due_date"]), due_time=row["due_time"],
                   done=row["done_at"] is not None, trip_ref=trip_refs.get(row["trip_id"]))
    elif kind == "expense":
        out.update(amount_cents=row["amount_cents"], date=_iso(row["date"]),
                   category=row["category"], description=row["description"],
                   trip_ref=trip_refs.get(row["trip_id"]))
    elif kind == "trip":
        out.update(name=row["name"], start_date=_iso(row["start_date"]),
                   end_date=_iso(row["end_date"]), budget_cents=row["budget_cents"])
    elif kind == "note":
        out.update(text=row["text"], suggestions=row["suggestions"],
                   capture_id=str(row["capture_id"]))
    return out


def changes(conn: psycopg.Connection, user_id: int, since: int) -> Dict[str, Any]:
    user = conn.execute("SELECT email, tz, monthly_budget_cents, seq FROM app_user "
                        "WHERE id = %s", (user_id,)).fetchone()
    trip_refs = {t["id"]: t["ref"] for t in conn.execute(
        "SELECT id, ref FROM trip WHERE user_id = %s", (user_id,)).fetchall()}
    items, deleted = [], []
    for kind in ("trip", "task", "expense", "note"):
        rows = conn.execute(f"SELECT * FROM {kind} WHERE user_id = %s AND updated_seq > %s "
                            "ORDER BY updated_seq, id", (user_id, since)).fetchall()
        for row in rows:
            if row.get("deleted_at"):
                deleted.append({"kind": kind, "id": row["id"]})
            else:
                items.append(row_view(kind, row, trip_refs))
    return {"items": items, "deleted": deleted, "seq": user["seq"],
            "me": {"email": user["email"], "tz": user["tz"],
                   "monthly_budget_cents": user["monthly_budget_cents"]}}


# --------------------------------------------------------------------------- the Filer

def _next_ref(conn: psycopg.Connection, user_id: int, kind: str) -> str:
    n = conn.execute("UPDATE app_user SET next_ref = next_ref + 1 WHERE id = %s "
                     "RETURNING next_ref - 1 AS n", (user_id,)).fetchone()["n"]
    return f"{PREFIX_OF_KIND[kind]}{n}"


def _trip_id(conn: psycopg.Connection, user_id: int, ref: Optional[str]) -> Optional[int]:
    if not ref:
        return None
    row = _item(conn, user_id, ref)
    if not row or row["kind"] != "trip":
        raise FilingConflict(f"no trip {ref}")
    return row["id"]


def _line(kind: str, tag: str, text: str, item: Optional[Dict[str, Any]] = None,
          undo: bool = True, **extra: Any) -> Dict[str, Any]:
    out = {"kind": kind, "tag": tag, "text": text, "undo": undo and item is not None}
    if item is not None:
        out["item"] = item
    out.update(extra)
    return out


def describe(kind: str, fields: Dict[str, Any], today: date, trip_name: Optional[str] = None) -> str:
    if kind == "expense":
        parts = [f"Expense {euros(fields['amount_cents'])}", fields["category"],
                 day_label(fields["date"], today)]
        if trip_name:
            parts.append(f"{trip_name} trip")
        return " · ".join(p for p in parts if p)
    if kind == "task":
        when = day_label(fields.get("due_date"), today)
        if when and fields.get("due_time"):
            when = f"{when} {fields['due_time']}"
        return f"Task “{fields['title']}”" + (f" · {when}" if when else "")
    if kind == "trip":
        start, end = date.fromisoformat(str(fields["start_date"])), \
            date.fromisoformat(str(fields["end_date"]))
        span = f"{start.day}–{end.day} {MONTHS[end.month - 1]}" if start.month == end.month \
            else f"{start.day} {MONTHS[start.month - 1]} – {end.day} {MONTHS[end.month - 1]}"
        budget = f" · budget {euros(fields['budget_cents'])}" if fields.get("budget_cents") else ""
        return f"Trip {fields['name']} · {span}{budget}"
    return str(fields)


def apply_batch(conn: psycopg.Connection, user: Dict[str, Any], capture: Dict[str, Any],
                ops: List[Dict[str, Any]], *, today: date, model: str,
                prompt_version: str) -> Tuple[int, int, List[Dict[str, Any]], str]:
    """Apply validated ops inside the caller's transaction (which holds the user's row lock).
    Returns (batch id, new seq, log lines, capture status)."""
    uid = user["id"]
    seq = conn.execute("UPDATE app_user SET seq = seq + 1 WHERE id = %s RETURNING seq",
                       (uid,)).fetchone()["seq"]
    batch_id = conn.execute(
        "INSERT INTO batch (user_id, capture_id, prompt_version, model) VALUES (%s, %s, %s, %s) "
        "RETURNING id", (uid, capture["capture_id"], prompt_version, model)).fetchone()["id"]
    lines: List[Dict[str, Any]] = []
    status = "filed"

    def undo(kind: str, item_id: int, inverse: Dict[str, Any], rev: int) -> None:
        conn.execute("INSERT INTO undo_entry (batch_id, item_kind, item_id, inverse_op, after_rev) "
                     "VALUES (%s, %s, %s, %s, %s)", (batch_id, kind, item_id, json.dumps(inverse), rev))

    for op in ops:
        kind = op["op"]
        if kind == "create_task":
            ref = _next_ref(conn, uid, "task")
            row = conn.execute(
                "INSERT INTO task (user_id, ref, title, due_date, due_time, created_batch_id, "
                "updated_seq) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (uid, ref, op["title"], op.get("due_date"), op.get("due_time"), batch_id, seq)).fetchone()
            undo("task", row["id"], {"op": "delete", "ref": ref}, 1)
            lines.append(_line("task", "Task", describe("task", op, today),
                               {"kind": "task", "id": row["id"], "ref": ref}))
        elif kind == "create_expense":
            ref = _next_ref(conn, uid, "expense")
            trip_id = _trip_id(conn, uid, op.get("trip_ref"))
            row = conn.execute(
                "INSERT INTO expense (user_id, ref, amount_cents, date, category, description, "
                "trip_id, trip_link, created_batch_id, updated_seq) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (uid, ref, op["amount_cents"], op["date"], op["category"], op["description"],
                 trip_id, "named" if trip_id else "none", batch_id, seq)).fetchone()
            undo("expense", row["id"], {"op": "delete", "ref": ref}, 1)
            trip = _item(conn, uid, op["trip_ref"]) if trip_id else None
            lines.append(_line("expense", "Spent",
                               describe("expense", op, today, trip and trip["name"]),
                               {"kind": "expense", "id": row["id"], "ref": ref}))
        elif kind == "create_trip":
            ref = _next_ref(conn, uid, "trip")
            row = conn.execute(
                "INSERT INTO trip (user_id, ref, name, start_date, end_date, budget_cents, "
                "created_batch_id, updated_seq) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "RETURNING id",
                (uid, ref, op["name"], op["start_date"], op["end_date"], op.get("budget_cents"),
                 batch_id, seq)).fetchone()
            undo("trip", row["id"], {"op": "delete", "ref": ref}, 1)
            lines.append(_line("trip", "Trip", describe("trip", op, today),
                               {"kind": "trip", "id": row["id"], "ref": ref}))
        elif kind in ("update", "delete", "complete_task"):
            item = _item(conn, uid, op["ref"])
            if item is None:
                raise FilingConflict(f"no item {op['ref']}")
            ik, table = item["kind"], TABLE[item["kind"]]
            rev = item["rev"] + 1
            ident = {"kind": ik, "id": item["id"], "ref": item["ref"]}
            if kind == "delete":
                conn.execute(f"UPDATE {table} SET deleted_at = now(), rev = %s, updated_seq = %s "
                             "WHERE id = %s", (rev, seq, item["id"]))
                undo(ik, item["id"], {"op": "restore", "ref": item["ref"]}, rev)
                lines.append(_line(ik, "Deleted", f"Deleted {_short(item)}", ident))
            elif kind == "complete_task":
                conn.execute("UPDATE task SET done_at = now(), rev = %s, updated_seq = %s "
                             "WHERE id = %s", (rev, seq, item["id"]))
                undo("task", item["id"], {"op": "reopen", "ref": item["ref"]}, rev)
                lines.append(_line("task", "Done", f"Done: {item['title']}", ident))
            else:
                changes_ = dict(op["set"])
                columns, values, old = [], [], {}
                if "trip_ref" in changes_:
                    trip_id = _trip_id(conn, uid, changes_.pop("trip_ref"))
                    old["trip_ref"] = None
                    columns += ["trip_id", "trip_link"]
                    values += [trip_id, "named" if trip_id else "none"]
                for name, value in changes_.items():
                    old[name] = _iso(item[name])
                    columns.append(name)
                    values.append(value)
                sets = ", ".join(f"{c} = %s" for c in columns)
                conn.execute(f"UPDATE {table} SET {sets}, rev = %s, updated_seq = %s WHERE id = %s",
                             (*values, rev, seq, item["id"]))
                undo(ik, item["id"], {"op": "update", "ref": item["ref"], "set": old}, rev)
                after = {**{k: _iso(item[k]) for k in FIELDS[ik]}, **changes_}
                tag = "Moved" if set(changes_) & {"due_date", "due_time", "start_date",
                                                   "end_date", "date"} else "Fixed"
                lines.append(_line(ik, tag, describe(ik, after, today), ident))
        elif kind == "set_monthly_budget":
            old = user.get("monthly_budget_cents")
            conn.execute("UPDATE app_user SET monthly_budget_cents = %s WHERE id = %s",
                         (op["amount_cents"], uid))
            user["monthly_budget_cents"] = op["amount_cents"]
            undo("budget", uid, {"op": "set_monthly_budget", "amount_cents": old}, 0)
            lines.append(_line("budget", "Budget",
                               f"Monthly budget {euros(op['amount_cents'])}",
                               {"kind": "budget", "id": uid, "ref": None}))
        elif kind == "note":
            status = "note"
            suggestions = (op.get("suggestions") or [])[:3]
            row = conn.execute(
                "INSERT INTO note (user_id, capture_id, text, suggestions, updated_seq) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (uid, capture["capture_id"], op.get("text") or capture["text"],
                 json.dumps(suggestions), seq)).fetchone()
            lines.append(_line("note", "Note", "Saved as a note. Is it one of these?",
                               {"kind": "note", "id": row["id"], "ref": None}, undo=False,
                               suggestions=[s.get("label") for s in suggestions]))
    return batch_id, seq, lines, status


def _short(item: Dict[str, Any]) -> str:
    if item["kind"] == "expense":
        return f"expense {euros(item['amount_cents'])} {item['description']}"
    if item["kind"] == "task":
        return f"task “{item['title']}”"
    return f"trip {item['name']}"
