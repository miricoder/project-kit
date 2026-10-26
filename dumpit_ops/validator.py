"""Validator: the rules every proposed batch must pass before it reaches the store.

docs/spec.md, "Validator rules". A batch with any invalid op is rejected whole and the
capture becomes a note; nothing is ever partially applied. The phone runs a TypeScript port
of this module; the eval harness and the service tests run this one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from .schema import (CATEGORIES, CHANGE_KINDS, CREATE_FIELDS, UPDATABLE, parse_date,
                     ref_kind, shape_problems)

MIN_CENTS = 1                      # €0.01
MAX_CENTS = 10_000_000             # €100,000
MAX_CHANGES = 5
YEARS_BACK, YEARS_AHEAD = 2, 5
PASTE_KINDS = (*CREATE_FIELDS, "note")


@dataclass
class Context:
    """The items the capture may refer to, keyed by ref (the request's context snapshot)."""
    tasks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    expenses: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    trips: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_snapshot(cls, snapshot: Optional[Dict[str, Any]]) -> "Context":
        snapshot = snapshot or {}
        return cls(*({item["ref"]: item for item in snapshot.get(key) or []}
                     for key in ("tasks", "expenses", "trips")))

    def item(self, ref: str) -> Optional[Dict[str, Any]]:
        table = {"task": self.tasks, "expense": self.expenses, "trip": self.trips}
        return table[ref_kind(ref)].get(ref)


@dataclass
class Result:
    ok: bool
    ops: List[Dict[str, Any]]           # normalised ops when ok, else []
    problems: List[str]


def _shift_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:                  # 29 February in a non-leap target year
        return day.replace(year=day.year + years, day=28)


def _normalise(op: Dict[str, Any]) -> Dict[str, Any]:
    """Unknown categories fall back to Other rather than rejecting the batch."""
    op = dict(op)
    if op["op"] == "create_expense" and op["category"] not in CATEGORIES:
        op["category"] = "Other"
    if op["op"] == "update" and "category" in op["set"] \
            and op["set"]["category"] not in CATEGORIES:
        op["set"] = {**op["set"], "category": "Other"}
    return op


def _effective(op: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
    """The fields an item will have after this op: for an update, the old item plus set."""
    if op["op"] != "update":
        return op
    return {**(ctx.item(op["ref"]) or {}), **op["set"]}


def validate(ops: Any, *, source: str, today: date, context: Context) -> Result:
    problems = shape_problems(ops)
    if problems:
        return Result(False, [], problems)
    if not ops:
        return Result(False, [], ["nothing to file"])

    earliest, latest = _shift_years(today, -YEARS_BACK), _shift_years(today, YEARS_AHEAD)
    changes = sum(op["op"] in CHANGE_KINDS for op in ops)
    if changes > MAX_CHANGES:
        problems.append(f"{changes} changes to existing items; at most {MAX_CHANGES}")

    for i, op in enumerate(ops):
        where = f"ops[{i}] {op['op']}"
        kind = op["op"]
        if source == "paste" and kind not in PASTE_KINDS:
            problems.append(f"{where}: a paste may only create items")

        ref = op.get("ref")
        if ref is not None:
            if context.item(ref) is None:
                problems.append(f"{where}: no item {ref}")
            elif kind == "complete_task" and ref_kind(ref) != "task":
                problems.append(f"{where}: {ref} is not a task")
        trip_ref = op.get("trip_ref", (op.get("set") or {}).get("trip_ref"))
        if trip_ref is not None and (ref_kind(trip_ref) != "trip"
                                     or context.item(trip_ref) is None):
            problems.append(f"{where}: no trip {trip_ref}")

        values = op.get("set", op)
        for name in ("amount_cents", "budget_cents"):
            if name in values and not MIN_CENTS <= values[name] <= MAX_CENTS:
                problems.append(f"{where}: {name} {values[name]} is outside "
                                f"{MIN_CENTS}..{MAX_CENTS}")
        for name in ("date", "due_date", "start_date", "end_date"):
            if name in values and not earliest <= parse_date(values[name]) <= latest:
                problems.append(f"{where}: {name} {values[name]} is outside "
                                f"{earliest}..{latest}")

        if kind == "update" and ref is not None and context.item(ref) is None:
            continue                     # nothing to merge with
        item = _effective(op, context)
        if kind in ("create_trip", "update") and "start_date" in item and "end_date" in item \
                and parse_date(item["end_date"]) < parse_date(item["start_date"]):
            problems.append(f"{where}: trip ends before it starts")
        if kind in ("create_task", "update") and item.get("due_time") \
                and not item.get("due_date"):
            problems.append(f"{where}: a due time needs a due date")

    if problems:
        return Result(False, [], problems)
    return Result(True, [_normalise(op) for op in ops], [])


def decide(text: str, ops: Any, *, source: str, today: date,
           context: Context) -> tuple[List[Dict[str, Any]], Result]:
    """The ops to apply for a capture: the validated batch, or a single note keeping the
    words when the batch is rejected. Suggestions from a proposed note are kept; they are
    only ever applied when the user taps one."""
    result = validate(ops, source=source, today=today, context=context)
    if result.ok:
        return result.ops, result
    suggestions: List[Dict[str, Any]] = []
    if isinstance(ops, list):
        for op in ops:
            if isinstance(op, dict) and op.get("op") == "note" \
                    and not shape_problems([op]):
                suggestions = list(op.get("suggestions") or [])
                break
    return [{"op": "note", "text": text, "suggestions": suggestions}], result
