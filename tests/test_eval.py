"""Slice 2: the filing test set and its scorer, with the model stubbed.

Scenario: filing test set reports a fully-correct score (docs/acceptance.feature).
"""
import io
import json
from datetime import date

import pytest

from dumpit_ops import Context, differences, fully_correct, validate
from eval import score
from service.model import ModelReply

CASES = score.load()
BY_ID = {case["id"]: case for case in CASES}


def by_text(text):
    return next(case for case in CASES if case["text"] == text)


class OracleModel:
    """Answers every capture with its expected ops, or with what `override` says."""
    name = "oracle"

    def __init__(self, override=None):
        self.override = override or {}

    def propose(self, request):
        ops = self.override.get(request["capture_id"], BY_ID[request["capture_id"]]
                                ["expected_ops"])
        return ModelReply(ops, 1000, 200)


def run(cases, model, tmp_path):
    out = io.StringIO()
    report = tmp_path / "report.json"
    data = score.run(cases, score.in_process_filer(model), model_name=model.name,
                     prompt_version="test", report=report, out=out)
    return data, out.getvalue(), json.loads(report.read_text())


# ---- the test set ---------------------------------------------------------------------

def test_every_case_is_well_formed():
    ids = [case["id"] for case in CASES]
    assert len(ids) == len(set(ids))
    for case in CASES:
        assert score.CASE_FIELDS <= set(case) <= score.CASE_FIELDS | score.OPTIONAL_FIELDS, \
            case["id"]
        assert case["source"] in ("typed", "paste") and case["author"].strip()
        date.fromisoformat(case["today"])
        assert case["text"].strip() and len(case["text"]) <= 4000


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_expected_ops_pass_the_validator(case):
    result = validate(case["expected_ops"], source=case["source"],
                      today=date.fromisoformat(case["today"]),
                      context=Context.from_snapshot(case["context"]))
    assert result.ok, result.problems


def test_the_builder_half_covers_every_kind():
    builder = [c for c in CASES if score.is_builder(c)]
    kinds = {score.case_kind(c) for c in builder}
    assert {"task", "expense", "trip", "edit", "paste", "note", "budget"} <= kinds
    assert sum(c["source"] == "paste" for c in builder) >= score.TARGET_PASTES
    assert len(builder) <= score.TARGET_CASES - score.TARGET_OTHERS


def test_shortfalls_name_what_the_set_still_lacks():
    builder = {"source": "typed", "author": "builder",
               "expected_ops": [{"op": "create_task", "title": "x"}]}
    gaps = score.shortfalls([builder] * 150)
    assert gaps == ["150 of 200 captures",
                    "0 of 50 captures written by someone other than the builder",
                    "0 of 3 pasted notes", "no expense captures", "no trip captures",
                    "no edit captures"]
    complete = [dict(c, author="ana") if i < 50 else c for i, c in enumerate(CASES)]
    complete += [dict(CASES[0], id=f"x{i}", author="ana") for i in range(50)]
    assert score.shortfalls(complete) == []


# ---- the scenario ---------------------------------------------------------------------

def test_scorer_reports_a_fully_correct_score(tmp_path):
    data, printed, report = run(CASES, OracleModel(), tmp_path)

    for kind in ("task", "expense", "trip", "edit", "paste"):
        assert f"  {kind:<8} 100.0 %" in printed
    assert "  overall  100.0 %" in printed
    assert "Written by the builder" in printed and "Written by others" in printed
    assert "Mean cost per capture: €0.00020" in printed   # 1000 in, 200 out tokens

    assert [r["id"] for r in report["results"]] == [c["id"] for c in CASES]
    assert all(r["correct"] for r in report["results"])
    assert report["summary"]["all"]["overall"]["share"] == 1.0
    assert report["summary"]["mean_cost_eur"] == pytest.approx(0.0002)
    assert report["model"] == "oracle"


# ---- what counts as fully correct -----------------------------------------------------

def test_a_wrong_amount_is_not_correct_and_is_explained(tmp_path):
    case = by_text("paid 42 for groceries")
    wrong = [dict(case["expected_ops"][0], amount_cents=4300)]
    data, printed, report = run([case], OracleModel({case["id"]: wrong}), tmp_path)
    result = report["results"][0]
    assert not result["correct"]
    assert result["diff"]["missing"][0][1] == ["amount_cents", 4200]
    assert "  expense    0.0 %  (0/1)" in printed


def test_wording_is_not_compared_but_structured_fields_are():
    expense = {"op": "create_expense", "amount_cents": 4200, "date": "2026-02-23",
               "category": "Groceries", "description": "Groceries"}
    assert fully_correct([{**expense, "description": "Supermarket run"}], [expense])
    assert not fully_correct([{**expense, "category": "Eating out"}], [expense])
    assert not fully_correct([{**expense, "trip_ref": "p1"}], [expense])
    assert not fully_correct([{**expense, "date": "2026-02-22"}], [expense])


def test_unknown_category_is_normalised_to_other_before_comparing():
    expense = {"op": "create_expense", "amount_cents": 500, "date": "2026-02-23",
               "category": "Other", "description": "Laundry"}
    assert fully_correct([{**expense, "category": "Laundry"}], [expense])


def test_order_does_not_matter_but_count_does():
    a = {"op": "create_task", "title": "A"}
    b = {"op": "create_task", "title": "B", "due_date": "2026-03-01"}
    assert fully_correct([b, a], [a, b])
    assert not fully_correct([a], [a, b])
    assert differences([a, a], [a]) == {"missing": [], "extra": [["create_task"]]}


def test_updates_compare_which_fields_change():
    expected = {"op": "update", "ref": "t5", "set": {"title": "Book barber"}}
    assert fully_correct([{**expected, "set": {"title": "Book the barber"}}], [expected])
    assert not fully_correct([{**expected, "ref": "t4"}], [expected])
    assert not fully_correct([{**expected, "set": {"title": "x", "due_date": "2026-03-01"}}],
                             [expected])


def test_a_rejected_batch_becomes_a_note_before_scoring(tmp_path):
    case = by_text("paid 0 for coffee")
    assert case["expected_ops"][0]["op"] == "note"
    bad = [{"op": "create_expense", "amount_cents": 0, "date": case["today"],
            "category": "Eating out", "description": "Coffee"}]
    data, printed, report = run([case], OracleModel({case["id"]: bad}), tmp_path)
    assert report["results"][0]["correct"]
    assert report["results"][0]["validator_problems"]


def test_service_errors_count_as_not_correct(tmp_path):
    case = CASES[0]
    broken = [{"op": "create_task"}]             # fails the shape check twice -> 502
    data, printed, report = run([case], OracleModel({case["id"]: broken}), tmp_path)
    result = report["results"][0]
    assert result["status"] == 502 and not result["correct"]
    assert "Service errors: 1" in printed


def test_others_are_reported_separately(tmp_path):
    cases = [CASES[0], dict(CASES[1], author="ana")]
    wrong = {cases[1]["id"]: [{"op": "note", "text": "?", "suggestions": []}]}
    data, printed, report = run(cases, OracleModel(wrong), tmp_path)
    assert data["summary"]["builder"]["overall"]["share"] == 1.0
    assert data["summary"]["others"]["overall"]["share"] == 0.0
    assert data["summary"]["all"]["overall"]["share"] == 0.5
