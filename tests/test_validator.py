"""Validator rules (docs/spec.md, "Validator rules") and the Slice 1 scenario."""
from datetime import date

import pytest

from dumpit_ops import Context, decide, validate

TODAY = date(2026, 2, 23)          # docs/acceptance.feature: Monday 23 February 2026


def expense(**over):
    op = {"op": "create_expense", "amount_cents": 4200, "date": "2026-02-23",
          "category": "Groceries", "description": "groceries"}
    return {**op, **over}


def ctx(**items):
    return Context.from_snapshot(items)


def check(ops, source="typed", context=None):
    return validate(ops, source=source, today=TODAY, context=context or Context())


# Scenario: implausible amount is not filed as an expense
def test_implausible_amount_is_not_filed_as_an_expense():
    text = "paid 4200000 for coffee"
    ops, result = decide(text, [expense(amount_cents=420_000_000, category="Eating out",
                                        description="coffee")],
                         source="typed", today=TODAY, context=Context())
    assert not result.ok
    assert [op["op"] for op in ops] == ["note"]           # no expense is created
    assert ops[0]["text"] == text                          # the capture is kept as a note


def test_a_plausible_expense_passes_unchanged():
    result = check([expense()])
    assert result.ok and result.ops == [expense()]


@pytest.mark.parametrize("cents,ok", [(0, False), (1, True), (10_000_000, True),
                                      (10_000_001, False), (-5, False)])
def test_amount_range(cents, ok):
    assert check([expense(amount_cents=cents)]).ok is ok


def test_amount_must_be_whole_cents():
    assert not check([expense(amount_cents=42.5)]).ok
    assert not check([expense(amount_cents=True)]).ok


@pytest.mark.parametrize("day,ok", [("2024-02-23", True), ("2024-02-22", False),
                                    ("2031-02-23", True), ("2031-02-24", False),
                                    ("2026-02-30", False), ("23/02/2026", False)])
def test_dates_are_real_and_within_two_years_back_five_ahead(day, ok):
    assert check([expense(date=day)]).ok is ok


def test_unknown_category_falls_back_to_other():
    result = check([expense(category="Supermarket")])
    assert result.ok and result.ops[0]["category"] == "Other"


def test_unknown_op_or_field_rejects_the_batch():
    assert not check([{"op": "send_email", "to": "x"}]).ok
    assert not check([expense(colour="red")]).ok
    assert not check([{"op": "create_task"}]).ok           # missing title


def test_an_empty_batch_is_not_filed():
    ops, result = decide("hmm", [], source="typed", today=TODAY, context=Context())
    assert not result.ok and ops[0]["op"] == "note"


def test_refs_must_exist():
    tasks = [{"ref": "t1", "title": "Dentist", "due_date": "2026-02-26", "due_time": "15:00"}]
    good = {"op": "update", "ref": "t1", "set": {"due_date": "2026-02-27"}}
    assert check([good], context=ctx(tasks=tasks)).ok
    assert not check([{**good, "ref": "t9"}], context=ctx(tasks=tasks)).ok


def test_update_fields_must_belong_to_the_item_kind():
    tasks = [{"ref": "t1", "title": "Dentist"}]
    assert not check([{"op": "update", "ref": "t1", "set": {"amount_cents": 5}}],
                     context=ctx(tasks=tasks)).ok


def test_complete_task_needs_a_task():
    expenses = [{"ref": "e1", "amount_cents": 4200, "date": "2026-02-23",
                 "category": "Groceries", "description": "groceries"}]
    assert not check([{"op": "complete_task", "ref": "e1"}],
                     context=ctx(expenses=expenses)).ok


def test_trip_ref_must_be_an_existing_trip():
    trips = [{"ref": "p1", "name": "Lisbon", "start_date": "2026-03-13",
              "end_date": "2026-03-16"}]
    assert check([expense(trip_ref="p1")], context=ctx(trips=trips)).ok
    assert not check([expense(trip_ref="p2")], context=ctx(trips=trips)).ok
    assert not check([expense(trip_ref="t1")],
                     context=ctx(tasks=[{"ref": "t1", "title": "x"}])).ok


def test_a_trip_cannot_end_before_it_starts():
    trip = {"op": "create_trip", "name": "Lisbon", "start_date": "2026-03-16",
            "end_date": "2026-03-13"}
    assert not check([trip]).ok
    trips = [{"ref": "p1", "name": "Lisbon", "start_date": "2026-03-13",
              "end_date": "2026-03-16"}]
    moved = {"op": "update", "ref": "p1", "set": {"start_date": "2026-03-20"}}
    assert not check([moved], context=ctx(trips=trips)).ok


def test_a_due_time_needs_a_due_date():
    assert not check([{"op": "create_task", "title": "Dentist", "due_time": "15:00"}]).ok
    assert check([{"op": "create_task", "title": "Dentist", "due_date": "2026-02-26",
                   "due_time": "15:00"}]).ok


def test_one_capture_cannot_change_more_than_five_items():
    tasks = [{"ref": f"t{i}", "title": f"Call {i}"} for i in range(6)]
    five = [{"op": "complete_task", "ref": f"t{i}"} for i in range(5)]
    assert check(five, context=ctx(tasks=tasks)).ok
    six = five + [{"op": "delete", "ref": "t5"}]
    assert not check(six, context=ctx(tasks=tasks)).ok


def test_a_paste_may_only_create():
    tasks = [{"ref": "t1", "title": "Dentist"}]
    assert check([expense(), {"op": "create_task", "title": "Renew gym"}], source="paste").ok
    assert not check([{"op": "delete", "ref": "t1"}, expense(amount_cents=1200)],
                     source="paste", context=ctx(tasks=tasks)).ok
    assert not check([{"op": "set_monthly_budget", "amount_cents": 140000}],
                     source="paste").ok


def test_a_note_keeps_at_most_three_suggestions():
    s = {"label": "Task: Marta", "op": {"op": "create_task", "title": "Marta"}}
    note = {"op": "note", "text": "the thing with Marta", "suggestions": [s] * 3}
    assert check([note]).ok
    assert not check([{**note, "suggestions": [s] * 4}]).ok
    nested = {"label": "x", "op": {"op": "note", "text": "y"}}
    assert not check([{**note, "suggestions": [nested]}]).ok


def test_a_rejected_batch_keeps_the_proposed_suggestions():
    s = {"label": "Task: Marta", "op": {"op": "create_task", "title": "Marta"}}
    proposed = [{"op": "note", "text": "the thing with Marta", "suggestions": [s]},
                expense(amount_cents=0)]
    ops, _ = decide("the thing with Marta", proposed, source="typed", today=TODAY,
                    context=Context())
    assert ops == [{"op": "note", "text": "the thing with Marta", "suggestions": [s]}]
