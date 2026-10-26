"""The op schema: the only changes the filing model can propose.

An op is a dict with an "op" key naming its kind, plus that kind's fields (docs/spec.md,
"Op schema"). `shape_problems` checks structure and types only; the semantic rules (refs
exist, ranges, paste limits) are in validator.py.
"""
from __future__ import annotations

import re
from datetime import date, time
from typing import Any, Dict, List, Tuple

CATEGORIES: Tuple[str, ...] = (
    "Groceries", "Eating out", "Transport", "Housing", "Bills",
    "Health", "Shopping", "Fun", "Travel", "Other",
)

MAX_TEXT = 500
MAX_SUGGESTIONS = 3

# Field name -> (type, required). Types: text, date, time, cents, category, ref.
Fields = Dict[str, Tuple[str, bool]]

CREATE_FIELDS: Dict[str, Fields] = {
    "create_task": {"title": ("text", True), "due_date": ("date", False),
                    "due_time": ("time", False)},
    "create_expense": {"amount_cents": ("cents", True), "date": ("date", True),
                       "category": ("category", True), "description": ("text", True),
                       "trip_ref": ("ref", False)},
    "create_trip": {"name": ("text", True), "start_date": ("date", True),
                    "end_date": ("date", True), "budget_cents": ("cents", False)},
}

OTHER_FIELDS: Dict[str, Fields] = {
    "update": {"ref": ("ref", True), "set": ("set", True)},
    "delete": {"ref": ("ref", True)},
    "complete_task": {"ref": ("ref", True)},
    "set_monthly_budget": {"amount_cents": ("cents", True)},
    "note": {"text": ("text", True), "suggestions": ("suggestions", False)},
}

FIELDS: Dict[str, Fields] = {**CREATE_FIELDS, **OTHER_FIELDS}
OP_KINDS: Tuple[str, ...] = tuple(FIELDS)
CHANGE_KINDS: Tuple[str, ...] = ("update", "delete", "complete_task")

# A ref's prefix says what it points at: t12 is a task, e88 an expense, p3 a trip.
REF_KINDS: Dict[str, str] = {"t": "task", "e": "expense", "p": "trip"}
UPDATABLE: Dict[str, Fields] = {
    "task": CREATE_FIELDS["create_task"],
    "expense": CREATE_FIELDS["create_expense"],
    "trip": CREATE_FIELDS["create_trip"],
}

_REF = re.compile(r"^[tep][0-9]+$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME = re.compile(r"^\d{2}:\d{2}$")


def ref_kind(ref: str) -> str:
    return REF_KINDS[ref[0]]


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _value_problem(kind: str, value: Any) -> str | None:
    if kind in ("text", "category"):
        if not isinstance(value, str) or not value.strip():
            return "must be non-empty text"
        if len(value) > MAX_TEXT:
            return f"must be at most {MAX_TEXT} characters"
        return None
    if kind == "cents":
        return None if isinstance(value, int) and not isinstance(value, bool) \
            else "must be a whole number of cents"
    if kind == "ref":
        return None if isinstance(value, str) and _REF.match(value) else "must be a ref like t12"
    if kind == "date":
        if not isinstance(value, str) or not _DATE.match(value):
            return "must be a date YYYY-MM-DD"
        try:
            date.fromisoformat(value)
        except ValueError:
            return "is not a real calendar date"
        return None
    if kind == "time":
        if not isinstance(value, str) or not _TIME.match(value):
            return "must be a time HH:MM"
        try:
            time.fromisoformat(value)
        except ValueError:
            return "is not a real time"
        return None
    raise AssertionError(kind)


def _fields_problems(where: str, op: Dict[str, Any], fields: Fields) -> List[str]:
    problems = []
    for name in op:
        if name != "op" and name not in fields:
            problems.append(f"{where}: unknown field {name!r}")
    for name, (kind, required) in fields.items():
        if name not in op:
            if required:
                problems.append(f"{where}: missing {name!r}")
            continue
        if kind == "set":
            problems += _set_problems(where, op)
        elif kind == "suggestions":
            problems += _suggestion_problems(where, op[name])
        else:
            problem = _value_problem(kind, op[name])
            if problem:
                problems.append(f"{where}: {name} {problem}")
    return problems


def _set_problems(where: str, op: Dict[str, Any]) -> List[str]:
    changes, ref = op.get("set"), op.get("ref")
    if not isinstance(changes, dict) or not changes:
        return [f"{where}: set must name at least one field"]
    if not (isinstance(ref, str) and _REF.match(ref)):
        return []                        # the ref problem is reported on its own
    allowed = UPDATABLE[ref_kind(ref)]
    problems = []
    for name, value in changes.items():
        if name not in allowed:
            problems.append(f"{where}: a {ref_kind(ref)} has no field {name!r}")
            continue
        problem = _value_problem(allowed[name][0], value)
        if problem:
            problems.append(f"{where}: set.{name} {problem}")
    return problems


def _suggestion_problems(where: str, suggestions: Any) -> List[str]:
    if not isinstance(suggestions, list):
        return [f"{where}: suggestions must be a list"]
    if len(suggestions) > MAX_SUGGESTIONS:
        return [f"{where}: at most {MAX_SUGGESTIONS} suggestions"]
    problems = []
    for i, item in enumerate(suggestions):
        at = f"{where}.suggestions[{i}]"
        if not isinstance(item, dict) or set(item) != {"label", "op"}:
            problems.append(f"{at}: must be {{label, op}}")
            continue
        if _value_problem("text", item["label"]):
            problems.append(f"{at}: label must be non-empty text")
        inner = item["op"]
        if isinstance(inner, dict) and inner.get("op") == "note":
            problems.append(f"{at}: a suggestion cannot be a note")
        else:
            problems += shape_problems([inner], prefix=at)
    return problems


def shape_problems(ops: Any, prefix: str = "ops") -> List[str]:
    """Structural problems with an op list; empty when every op is well formed."""
    if not isinstance(ops, list):
        return [f"{prefix}: must be a list"]
    problems = []
    for i, op in enumerate(ops):
        where = f"{prefix}[{i}]"
        if not isinstance(op, dict):
            problems.append(f"{where}: must be an object")
            continue
        kind = op.get("op")
        if kind not in FIELDS:
            problems.append(f"{where}: unknown op {kind!r}")
            continue
        problems += _fields_problems(f"{where} {kind}", op, FIELDS[kind])
    return problems
