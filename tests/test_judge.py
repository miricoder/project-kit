"""Tests for the judge panel: the form, the combination rule, the case, seating, and the
record step that a gate depends on.

Built against recorded verdict fixtures (tests/fixtures/verdicts), so nothing here calls a
live model. The transports are the only untested surface, and they are deliberately thin.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "handover" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "pipeline" / "scripts"))
sys.path.insert(0, str(ROOT / "scripts"))

import doctor  # noqa: E402
import form  # noqa: E402
import judge  # noqa: E402
import state  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "verdicts"
FORM_DOC = ROOT / "skills" / "handover" / "references" / "judge-form.md"


def fixture(name: str, case_id: str = "CASE") -> dict:
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    data["case_id"] = case_id
    return data


def seat(family: str, name: str, case_id: str = "CASE") -> dict:
    return {"family": family, "model": "m", "transport": "paste",
            "verdict": fixture(name, case_id)}


# --------------------------------------------------------------------------- the form

class ValidateTest(unittest.TestCase):
    def test_every_fixture_is_valid(self):
        for name in ("sound", "fix_first", "reject", "needs_info"):
            with self.subTest(fixture=name):
                self.assertEqual(form.validate(fixture(name), "CASE"), [])

    def test_a_verdict_for_another_case_is_refused(self):
        problems = form.validate(fixture("sound"), "OTHER")
        self.assertTrue(any("case_id" in p for p in problems))

    def test_every_criterion_must_be_rated_once(self):
        verdict = fixture("sound")
        verdict["criteria"] = verdict["criteria"][1:] + [verdict["criteria"][1]]
        problems = form.validate(verdict, "CASE")
        self.assertTrue(any("not rated: job_fit" in p for p in problems))
        self.assertTrue(any("appears twice" in p for p in problems))

    def test_a_concern_needs_a_note(self):
        verdict = fixture("sound")
        verdict["criteria"][0] = {"id": "job_fit", "rating": "concern", "note": ""}
        self.assertTrue(any("needs a note" in p for p in form.validate(verdict, "CASE")))

    def test_a_blocker_needs_a_fix(self):
        verdict = fixture("fix_first")
        verdict["findings"][0]["fix"] = " "
        self.assertTrue(any("needs a concrete fix" in p
                            for p in form.validate(verdict, "CASE")))

    def test_unknown_values_are_refused(self):
        verdict = fixture("fix_first")
        verdict["verdict"] = "PROBABLY FINE"
        verdict["findings"][0]["severity"] = "critical"
        verdict["findings"][0]["confidence"] = "SURE"
        problems = form.validate(verdict, "CASE")
        for word in ("verdict must be", "severity must be", "confidence must be"):
            self.assertTrue(any(word in p for p in problems), word)

    def test_the_verdict_must_agree_with_the_findings(self):
        sound = fixture("sound")
        sound["findings"].append(fixture("fix_first")["findings"][0])
        self.assertTrue(any("SOUND with a blocker" in p for p in form.validate(sound, "CASE")))

        fix_first = fixture("fix_first")
        fix_first["findings"] = fix_first["findings"][1:]
        self.assertTrue(any("FIX FIRST needs" in p for p in form.validate(fix_first, "CASE")))

        needs_info = fixture("needs_info")
        needs_info["questions"] = []
        self.assertTrue(any("NEEDS INFO needs" in p
                            for p in form.validate(needs_info, "CASE")))

        reject = fixture("reject")
        reject["findings"] = []
        self.assertTrue(any("REJECT needs" in p for p in form.validate(reject, "CASE")))

    def test_sound_with_a_failed_criterion_is_contradictory(self):
        verdict = fixture("sound")
        verdict["criteria"][0] = {"id": "job_fit", "rating": "fail", "note": "no"}
        self.assertTrue(any("failed criterion" in p for p in form.validate(verdict, "CASE")))


class ExtractTest(unittest.TestCase):
    def test_a_fenced_block_with_prose_around_it(self):
        reply = "Here is my verdict:\n```json\n{\"a\": 1}\n```\nThanks."
        self.assertEqual(form.extract(reply), {"a": 1})

    def test_a_bare_object_with_prose_around_it(self):
        self.assertEqual(form.extract('Sure. {"a": {"b": 2}} Done.'), {"a": {"b": 2}})

    def test_two_blocks_are_refused_rather_than_guessed(self):
        with self.assertRaisesRegex(form.FormError, "2 JSON blocks"):
            form.extract("```json\n{\"a\": 1}\n```\n```json\n{\"a\": 2}\n```")

    def test_no_json_and_bad_json_are_refused(self):
        for reply in ("", "looks fine to me", '{"a": 1,}'):
            with self.subTest(reply=reply):
                with self.assertRaises(form.FormError):
                    form.extract(reply)


class PanelTest(unittest.TestCase):
    def test_three_distinct_families_are_a_panel(self):
        self.assertEqual(form.check_panel(["openai", "google", "moonshot"]), [])

    def test_anthropic_never_sits(self):
        problems = form.check_panel(["anthropic", "google", "moonshot"])
        self.assertTrue(any("cannot judge" in p for p in problems))

    def test_one_family_cannot_hold_two_seats(self):
        problems = form.check_panel(["google", "google", "moonshot"])
        self.assertTrue(any("two seats" in p for p in problems))

    def test_two_seats_are_not_enough(self):
        self.assertTrue(form.check_panel(["google", "moonshot"]))


# --------------------------------------------------------------------------- combine

class CombineTest(unittest.TestCase):
    def test_a_lone_reject_cannot_sink_a_sound_majority(self):
        ruling = form.combine([seat("google", "sound"), seat("openai", "sound"),
                               seat("xai", "reject")])
        self.assertEqual(ruling["ruling"], "SOUND")
        self.assertEqual(ruling["open_fixes"], [])
        self.assertEqual([f["id"] for f in ruling["dissent_blockers"]], ["xai-1"])
        self.assertEqual([d["family"] for d in ruling["dissent"]], ["xai"])

    def test_a_lone_sound_cannot_pass_the_plan(self):
        ruling = form.combine([seat("google", "sound"), seat("moonshot", "fix_first"),
                               seat("xai", "reject")])
        self.assertEqual(ruling["ruling"], "FIX FIRST")
        self.assertFalse(form.passes(ruling["ruling"], ruling["open_fixes"]))

    def test_open_fixes_are_ranked_by_confidence_within_severity(self):
        ruling = form.combine([seat("google", "sound"), seat("moonshot", "fix_first"),
                               seat("xai", "reject")])
        self.assertEqual([f["id"] for f in ruling["open_fixes"]], ["moonshot-1", "xai-1"])
        self.assertEqual([f["id"] for f in ruling["recommended"]], ["moonshot-2"])
        self.assertEqual([f["id"] for f in ruling["minor"]], ["google-1"])

    def test_the_criteria_matrix_shows_every_judge(self):
        ruling = form.combine([seat("google", "sound"), seat("moonshot", "fix_first"),
                               seat("xai", "reject")])
        self.assertEqual(set(ruling["criteria"]), set(form.CRITERION_IDS))
        self.assertEqual(ruling["criteria"]["data_and_rollback"],
                         {"google": "pass", "moonshot": "fail", "xai": "pass"})

    def test_high_tier_downgrades_speculative_fix_first(self):
        speculative = fixture("fix_first")
        speculative["findings"][0]["confidence"] = "SPECULATING"
        seats = [seat("google", "sound"),
                 {"family": "moonshot", "verdict": speculative},
                 {"family": "xai", "verdict": dict(speculative)}]
        self.assertEqual(form.combine(seats, "standard")["ruling"], "FIX FIRST")
        high = form.combine(seats, "high")
        self.assertEqual(high["ruling"], "NEEDS INFO")
        self.assertTrue(high["downgraded"])

    def test_questions_are_collected_with_their_judge(self):
        ruling = form.combine([seat("google", "needs_info"), seat("openai", "needs_info"),
                               seat("xai", "sound")])
        self.assertEqual(ruling["ruling"], "NEEDS INFO")
        self.assertEqual(len(ruling["questions"]), 4)

    def test_verdicts_on_different_cases_do_not_combine(self):
        with self.assertRaisesRegex(form.FormError, "different versions"):
            form.combine([seat("google", "sound"), seat("openai", "sound"),
                          seat("xai", "sound", case_id="OTHER")])

    def test_an_invalid_panel_does_not_combine(self):
        with self.assertRaises(form.FormError):
            form.combine([seat("anthropic", "sound"), seat("openai", "sound"),
                          seat("xai", "sound")])

    def test_passes_agrees_with_the_state_gate(self):
        for ruling, fixes in (("SOUND", []), ("SOUND", ["x"]), ("FIX FIRST", []),
                              ("FIX FIRST", ["x"]), ("REJECT", []), ("NEEDS INFO", []),
                              ("SPLIT", [])):
            with self.subTest(ruling=ruling, fixes=fixes):
                st = state.new_state("p")
                state.record_ruling(st, "judge", ruling, 1, fixes)
                self.assertEqual(form.passes(ruling, fixes), state.gate_passed(st, "judge"))


# --------------------------------------------------------------------------- a project

SPEC = """# Spec

## Architecture

One app.

## Strongest counter-argument

Everything rests on filing accuracy that has never been measured on real captures, and
the design has no fallback if it plateaus.
"""


class ProjectCase(unittest.TestCase):
    """A temporary project with a complete design, isolated from the real registry."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "proj"
        (self.project / "docs").mkdir(parents=True)
        patcher = mock.patch.dict(os.environ, {
            "PROJECT_KIT_REGISTRY": str(Path(self.tmp.name) / "registry.json")})
        patcher.start()
        self.addCleanup(patcher.stop)
        for rel, text in (("docs/research.md", "# Research\n\nThe job.\n"),
                          ("docs/proposal.md", "# Proposal\n\nThe cut.\n"),
                          ("docs/spec.md", SPEC),
                          ("docs/acceptance.feature", "Feature: capture\n")):
            (self.project / rel).write_text(text)
        st = state.new_state("proj")
        for phase in ("ideate", "proposal", "design"):
            state.set_phase(st, phase, "complete")
        state.save(st, self.project)
        self.env = {"OPENAI_API_KEY": "k1", "GEMINI_API_KEY": "k2", "MOONSHOT_API_KEY": "k3"}
        for name, fake in (("load_panel_env", lambda: dict(self.env)),
                           ("codex_logged_in", lambda: False)):
            patcher = mock.patch.object(judge.doctor, name, fake)
            patcher.start()
            self.addCleanup(patcher.stop)

    def pk(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = judge.main(["-C", str(self.project), *args])
        try:
            payload = json.loads(out.getvalue()) if out.getvalue().strip() else None
        except json.JSONDecodeError:
            payload = None
        return code, payload, err.getvalue()

    def state(self):
        return state.load(self.project)

    def case_id(self, round_no=1):
        return json.loads((judge.round_dir(self.project, round_no) / "case.json")
                          .read_text())["case_id"]

    def replies(self, by_family):
        """A fake transport answering each family with a recorded fixture."""
        def transport(seat, brief, env):
            name = by_family[seat["family"]]
            text = json.dumps(fixture(name, self.case_id(judge.current_round(self.state()))))
            return "```json\n" + text + "\n```", 30000, 2000
        return mock.patch.dict(judge.TRANSPORTS, {"api_key": transport})


class CaseTest(ProjectCase):
    def test_the_case_id_is_stable_and_tracks_the_plan(self):
        st = self.state()
        first = judge.build_case(self.project, st, 1)["case_id"]
        self.assertEqual(first, judge.build_case(self.project, st, 1)["case_id"])
        (self.project / "docs/proposal.md").write_text("# Proposal\n\nA different cut.\n")
        self.assertNotEqual(first, judge.build_case(self.project, st, 1)["case_id"])

    def test_a_missing_document_is_refused(self):
        (self.project / "docs/acceptance.feature").unlink()
        with self.assertRaisesRegex(judge.JudgeError, "acceptance.feature"):
            judge.build_case(self.project, self.state(), 1)

    def test_a_template_counter_argument_is_refused(self):
        (self.project / "docs/spec.md").write_text(
            "# Spec\n\n## Strongest counter-argument\n\n<The most plausible case that this "
            "design is wrong.>\n")
        with self.assertRaisesRegex(judge.JudgeError, "counter-argument"):
            judge.build_case(self.project, self.state(), 1)

    def test_the_brief_carries_the_form_and_the_whole_plan(self):
        case = judge.build_case(self.project, self.state(), 1)
        brief = judge.render_brief(case)
        self.assertIn(case["case_id"], brief)
        for cid in form.CRITERION_IDS:
            self.assertIn(f"`{cid}`", brief)
        for verdict in form.VERDICTS:
            self.assertIn(f"`{verdict}`", brief)
        for _, rel in judge.DOCUMENTS:
            self.assertIn(f"BEGIN {rel}", brief)
        self.assertIn("never been measured", brief)
        self.assertIn("Anthropic", brief)

    def test_case_writes_this_rounds_files(self):
        code, out, _ = self.pk("case")
        self.assertEqual(code, 0)
        rdir = judge.round_dir(self.project, 1)
        self.assertTrue((rdir / "case.json").is_file())
        self.assertTrue((rdir / "brief.md").is_file())
        self.assertEqual(out["case_id"], self.case_id())


class SeatsTest(unittest.TestCase):
    def test_the_first_three_reachable_families_sit(self):
        seats, problems = judge.resolve_seats(
            {"OPENAI_API_KEY": "a", "GEMINI_API_KEY": "b", "MOONSHOT_API_KEY": "c",
             "XAI_API_KEY": "d"}, codex_ok=False)
        self.assertEqual(problems, [])
        self.assertEqual([s["family"] for s in seats], ["openai", "google", "moonshot"])
        self.assertTrue(all(s["transport"] == "api_key" for s in seats))

    def test_an_anthropic_key_never_fills_a_seat(self):
        seats, problems = judge.resolve_seats(
            {"ANTHROPIC_API_KEY": "a", "GEMINI_API_KEY": "b", "MOONSHOT_API_KEY": "c"},
            codex_ok=False)
        self.assertNotIn("anthropic", [s["family"] for s in seats])
        self.assertTrue(problems)

    def test_asking_for_anthropic_is_refused(self):
        _, problems = judge.resolve_seats({}, codex_ok=False,
                                          only=["anthropic", "google", "xai"])
        self.assertTrue(any("cannot judge" in p for p in problems))

    def test_codex_paste_and_unsupported_keys(self):
        seats, problems = judge.resolve_seats(
            {"COHERE_API_KEY": "a", doctor.PASTE_SEATS_KEY: "moonshot"}, codex_ok=True)
        self.assertEqual(problems, [])
        self.assertEqual({s["family"]: s["transport"] for s in seats},
                         {"openai": "cli", "moonshot": "paste", "cohere": "paste"})

    def test_paste_overrides_a_key(self):
        seats, _ = judge.resolve_seats(
            {"OPENAI_API_KEY": "a", "GEMINI_API_KEY": "b", "MOONSHOT_API_KEY": "c"},
            codex_ok=False, paste=["google"])
        self.assertEqual({s["family"]: s["transport"] for s in seats}["google"], "paste")

    def test_model_overrides_come_from_the_env(self):
        seats, _ = judge.resolve_seats(
            {"OPENAI_API_KEY": "a", "GEMINI_API_KEY": "b", "MOONSHOT_API_KEY": "c",
             "PROJECT_KIT_MODEL_OPENAI": "gpt-test"}, codex_ok=False)
        self.assertEqual(seats[0]["model"], "gpt-test")

    def test_a_price_override_is_used(self):
        self.assertEqual(judge.cost("openai", 1_000_000, 0,
                                    {"PROJECT_KIT_PRICE_OPENAI": "1,2"}), 1.0)


class RunTest(ProjectCase):
    def test_a_full_round_records_spend_and_valid_verdicts(self):
        self.pk("case")
        with self.replies({"openai": "sound", "google": "sound", "moonshot": "fix_first"}):
            code, out, err = self.pk("run")
        self.assertEqual(code, 0, err)
        self.assertEqual({r["status"] for r in out["results"]}, {"valid"})
        self.assertGreater(self.state()["budget"]["spent_usd"], 0)
        code, out, _ = self.pk("status")
        self.assertTrue(out["ready_to_combine"])

    def test_a_second_run_skips_seats_that_already_answered(self):
        self.pk("case")
        with self.replies({"openai": "sound", "google": "sound", "moonshot": "sound"}):
            self.pk("run")
            code, out, _ = self.pk("run")
        self.assertEqual(out["results"], [])
        self.assertEqual(sorted(out["already_valid"]), ["google", "moonshot", "openai"])

    def test_the_budget_cap_refuses_before_any_call(self):
        self.pk("case")
        st = self.state()
        st["budget"]["max_usd"] = 0.0001
        state.save(st, self.project)
        called = []
        with mock.patch.dict(judge.TRANSPORTS,
                             {"api_key": lambda *a: called.append(a) or ("", 0, 0)}):
            code, _, err = self.pk("run")
        self.assertEqual(code, 1)
        self.assertIn("cap", err)
        self.assertEqual(called, [])

    def test_an_invalid_reply_is_kept_but_not_counted(self):
        self.pk("case")
        with mock.patch.dict(judge.TRANSPORTS,
                             {"api_key": lambda seat, b, e: ("I think it is fine.", 10, 10)}):
            code, out, _ = self.pk("run")
        self.assertEqual(code, 1)
        self.assertEqual({r["status"] for r in out["results"]}, {"invalid"})
        self.assertTrue((judge.round_dir(self.project, 1) / "raw" / "openai.txt").is_file())
        _, status, _ = self.pk("status")
        self.assertFalse(status["ready_to_combine"])

    def test_a_failed_seat_is_reported(self):
        self.pk("case")

        def down(seat, brief, env):
            raise judge.TransportError("no credit or quota")
        with mock.patch.dict(judge.TRANSPORTS, {"api_key": down}):
            code, out, _ = self.pk("run")
        self.assertEqual(code, 1)
        self.assertEqual(out["results"][0]["reason"], "no credit or quota")


class AcceptTest(ProjectCase):
    def write(self, name, case_id=None):
        path = Path(self.tmp.name) / f"{name}.txt"
        path.write_text("Verdict below.\n" + json.dumps(fixture(name, case_id or self.case_id())))
        return path

    def test_a_pasted_reply_is_validated(self):
        self.pk("case")
        code, out, _ = self.pk("accept", "--family", "google", "--file", str(self.write("sound")))
        self.assertEqual(code, 0)
        self.assertEqual(out["verdict"], "SOUND")

    def test_a_pasted_reply_for_another_case_is_refused(self):
        self.pk("case")
        code, _, err = self.pk("accept", "--family", "google", "--file",
                               str(self.write("sound", case_id="stale")))
        self.assertEqual(code, 1)
        self.assertIn("case_id", err)

    def test_anthropic_cannot_be_accepted(self):
        self.pk("case")
        code, _, err = self.pk("accept", "--family", "anthropic", "--file",
                               str(self.write("sound")))
        self.assertEqual(code, 1)
        self.assertIn("cannot judge", err)


class RecordTest(ProjectCase):
    def judged(self, by_family):
        self.pk("case")
        with self.replies(by_family):
            self.pk("run")
        return self.pk("combine")

    def test_a_sound_majority_opens_the_gate(self):
        code, out, _ = self.judged({"openai": "sound", "google": "sound", "moonshot": "reject"})
        self.assertEqual((code, out["ruling"]), (0, "SOUND"))
        self.assertTrue((self.project / "docs" / "ruling.md").is_file())
        code, out, err = self.pk("record")
        self.assertEqual(code, 0, err)
        self.assertTrue(out["passed"])
        self.assertTrue(state.gate_passed(self.state(), "judge"))

    def test_fix_first_keeps_the_gate_closed_with_its_fixes(self):
        self.judged({"openai": "sound", "google": "fix_first", "moonshot": "reject"})
        code, out, _ = self.pk("record")
        self.assertEqual(code, 0)
        self.assertFalse(out["passed"])
        fixes = self.state()["gates"]["judge"]["open_fixes"]
        self.assertTrue(fixes[0].startswith("google-1: "))
        self.assertIn("judge gate has not passed",
                      " ".join(state.blockers(self.state(), "initiate")))

    def test_a_hand_edited_ruling_is_refused(self):
        self.judged({"openai": "fix_first", "google": "fix_first", "moonshot": "sound"})
        path = judge.round_dir(self.project, 1) / "ruling.json"
        ruling = json.loads(path.read_text())
        ruling["ruling"], ruling["open_fixes"] = "SOUND", []
        path.write_text(json.dumps(ruling))
        code, _, err = self.pk("record")
        self.assertEqual(code, 1)
        self.assertIn("disagrees", err)
        self.assertFalse(state.gate_passed(self.state(), "judge"))

    def test_a_plan_edited_after_judging_is_refused(self):
        self.judged({"openai": "sound", "google": "sound", "moonshot": "sound"})
        (self.project / "docs/spec.md").write_text(SPEC + "\nA late change.\n")
        code, _, err = self.pk("record")
        self.assertEqual(code, 1)
        self.assertIn("changed after", err)

    def test_round_two_must_answer_every_open_fix(self):
        self.judged({"openai": "fix_first", "google": "fix_first", "moonshot": "sound"})
        self.pk("record")
        code, _, err = self.pk("case")
        self.assertEqual(code, 1)
        self.assertIn("changes.md", err)
        (self.project / "docs/changes.md").write_text("google-1: added a reverse migration.\n")
        code, _, err = self.pk("case")
        self.assertEqual(code, 1)
        self.assertIn("openai-1", err)
        (self.project / "docs/changes.md").write_text(
            "google-1: added a reverse migration.\nopenai-1: same fix, see spec Rollback.\n")
        code, out, err = self.pk("case")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["round"], 2)
        brief = (judge.round_dir(self.project, 2) / "brief.md").read_text()
        self.assertIn("Previous round (1): FIX FIRST", brief)
        self.assertIn("added a reverse migration", brief)

    def test_rounds_are_bounded(self):
        st = self.state()
        for n in range(1, judge.MAX_ROUNDS + 1):
            state.record_ruling(st, "judge", "REJECT", n, [])
        state.save(st, self.project)
        code, _, err = self.pk("case")
        self.assertEqual(code, 1)
        self.assertIn("allow-extra-round", err)

    def test_the_round_limit_can_be_raised_but_not_past_the_ceiling(self):
        st = self.state()
        for n in range(1, judge.MAX_ROUNDS + 1):
            state.record_ruling(st, "judge", "REJECT", n, [])
        state.save(st, self.project)
        code, out, _ = self.pk("rounds", "5")
        self.assertEqual((code, out["max_rounds"], out["rounds_left"]), (0, 5, 2))
        code, _, err = self.pk("case")
        self.assertNotIn("allow-extra-round", err)
        code, _, err = self.pk("rounds", str(judge.HARD_MAX_ROUNDS + 1))
        self.assertEqual(code, 1)
        self.assertIn("must be 1..", err)

    def test_combine_needs_three_valid_verdicts(self):
        self.pk("case")
        code, _, err = self.pk("combine")
        self.assertEqual(code, 1)
        self.assertIn("0 valid verdict", err)


# --------------------------------------------------------------------------- consistency

class ConsistencyTest(unittest.TestCase):
    """The human-readable form, the doctor and the panel must agree with form.py."""

    def test_the_form_page_matches_the_code(self):
        text = FORM_DOC.read_text()
        for cid, question in form.CRITERIA:
            self.assertIn(f"| `{cid}` | {question} |", text)
        for word in form.VERDICTS + form.SEVERITIES + form.CONFIDENCES + form.RATINGS:
            self.assertIn(f"`{word}`", text)

    def test_families_agree_with_the_doctor(self):
        self.assertEqual(set(form.FAMILIES),
                         set(doctor.FAMILY_BY_KEY.values()) - {form.EXCLUDED_FAMILY})
        self.assertEqual(form.EXCLUDED_FAMILY, doctor.EXCLUDED_FAMILY)
        self.assertEqual(form.SEATS_REQUIRED, doctor.SEATS_REQUIRED)

    def test_every_api_family_has_a_price(self):
        self.assertEqual(set(judge.API_SPECS), set(judge.PRICES))
        self.assertTrue(set(judge.API_SPECS) <= set(form.FAMILIES))


if __name__ == "__main__":
    unittest.main()
