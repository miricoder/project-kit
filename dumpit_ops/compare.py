"""Fully-correct comparison of two op lists, for the eval harness (docs/spec.md, "Eval
harness"). Both lists must already have passed the Validator.

A capture is filed fully correctly when, after Validator normalisation, the filed ops and the
expected ops are the same multiset of *structured* facts: the op kind, the ref it touches,
amounts, dates and times, the category and the trip link. Free text (titles, descriptions,
trip names, note text) is not compared: wording varies and is not what the person checks in
the one-line confirmation. For an update, the names of the fields it sets are compared, and
the values of the structured ones.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Tuple

from .validator import _normalise as normalise

FREE_TEXT = ("title", "description", "name", "text")
STRUCTURED = ("ref", "amount_cents", "budget_cents", "date", "due_date", "due_time",
              "start_date", "end_date", "category", "trip_ref")


def key(op: Dict[str, Any]) -> Tuple:
    """The facts of one validated op that must match; a note matches any note."""
    op = normalise(op)
    kind = op.get("op")
    if kind == "note":
        return ("note",)
    facts: List[Tuple[str, Any]] = [(name, op[name]) for name in STRUCTURED if name in op]
    if kind == "update":
        changes = op.get("set") or {}
        facts += [(f"set.{name}", None if name in FREE_TEXT else value)
                  for name, value in sorted(changes.items())]
    return (kind, *facts)


def _sorted_keys(ops: Iterable[Dict[str, Any]]) -> List[str]:
    return sorted(json.dumps(key(op), sort_keys=True, default=str) for op in ops)


def fully_correct(filed: List[Dict[str, Any]], expected: List[Dict[str, Any]]) -> bool:
    return _sorted_keys(filed) == _sorted_keys(expected)


def differences(filed: List[Dict[str, Any]], expected: List[Dict[str, Any]]) -> Dict[str, List]:
    """What is missing from the filed ops and what is extra, as op keys; empty when equal."""
    got, want = _sorted_keys(filed), _sorted_keys(expected)
    missing, extra = list(want), []
    for item in got:
        if item in missing:
            missing.remove(item)
        else:
            extra.append(item)
    return {"missing": [json.loads(m) for m in missing],
            "extra": [json.loads(e) for e in extra]}
