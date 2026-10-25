"""Tests for the environment doctor.

The panel rules and the transient-versus-broken distinction are the parts that would
mislead a user if wrong, so they are tested directly. Everything here is pure: no network,
no subprocess.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import doctor  # noqa: E402


class ParseVersionTest(unittest.TestCase):
    def test_reads_major_minor_patch(self):
        self.assertEqual(doctor.parse_version("2.1.266 (Claude Code)"), (2, 1, 266))

    def test_defaults_missing_patch_to_zero(self):
        self.assertEqual(doctor.parse_version("Python 3.13"), (3, 13, 0))

    def test_returns_none_when_absent(self):
        self.assertIsNone(doctor.parse_version("no version here"))
        self.assertIsNone(doctor.parse_version(""))

    def test_old_cli_sorts_below_the_minimum(self):
        self.assertLess(doctor.parse_version("0.2.56"), doctor.MIN_CLAUDE)


class ParseEnvFileTest(unittest.TestCase):
    def test_reads_pairs_and_skips_comments_and_blanks(self):
        parsed = doctor.parse_env_file(
            "# a comment\n\nFOO=bar\n  BAZ = qux  \nnot-a-pair\n")
        self.assertEqual(parsed, {"FOO": "bar", "BAZ": "qux"})

    def test_strips_one_matching_quote_pair(self):
        self.assertEqual(doctor.parse_env_file('K="v"')["K"], "v")
        self.assertEqual(doctor.parse_env_file("K='v'")["K"], "v")

    def test_keeps_inner_equals(self):
        self.assertEqual(doctor.parse_env_file("K=a=b")["K"], "a=b")


class ClassifyTest(unittest.TestCase):
    """A 503 from an overloaded model must not read as a dead seat; a 429 that says
    'insufficient balance' must."""

    def test_200_is_ok(self):
        self.assertEqual(doctor.classify("200", "{}")[0], "ok")

    def test_quota_wording_is_billing_even_on_429(self):
        verdict, _ = doctor.classify(
            "429", '{"error":{"message":"account is suspended due to insufficient balance"}}')
        self.assertEqual(verdict, "billing")

    def test_bare_429_without_billing_wording_is_transient(self):
        self.assertEqual(doctor.classify("429", "slow down")[0], "transient")

    def test_503_is_transient(self):
        self.assertEqual(doctor.classify("503", "high demand")[0], "transient")

    def test_no_response_is_transient(self):
        self.assertEqual(doctor.classify("000", "")[0], "transient")

    def test_401_and_403_are_auth(self):
        for status in ("401", "403"):
            with self.subTest(status=status):
                self.assertEqual(doctor.classify(status, "nope")[0], "auth")

    def test_google_quota_message_is_billing(self):
        verdict, _ = doctor.classify(
            "429", "You exceeded your current quota, please check your plan and billing")
        self.assertEqual(verdict, "billing")


class PanelSeatsTest(unittest.TestCase):
    def seats(self, env):
        """panel_seats consults the codex CLI; neutralise that so tests stay pure."""
        real = doctor.shutil.which
        doctor.shutil.which = lambda name: None if name == "codex" else real(name)
        try:
            return doctor.panel_seats(env)
        finally:
            doctor.shutil.which = real

    def test_three_distinct_families_satisfy_the_panel(self):
        families, _, problems = self.seats({
            "MOONSHOT_API_KEY": "a", "GEMINI_API_KEY": "b", "XAI_API_KEY": "c"})
        self.assertEqual(sorted(families), ["google", "moonshot", "xai"])
        self.assertEqual(problems, [])

    def test_two_keys_from_one_family_fill_one_seat(self):
        families, notes, problems = self.seats({
            "GEMINI_API_KEY": "a", "GOOGLE_API_KEY": "b"})
        self.assertEqual(families, ["google"])
        self.assertTrue(any("duplicates" in n for n in notes))
        self.assertTrue(problems)

    def test_anthropic_is_excluded_and_reported(self):
        families, _, problems = self.seats({
            "ANTHROPIC_API_KEY": "a", "GEMINI_API_KEY": "b", "MOONSHOT_API_KEY": "c"})
        self.assertNotIn("anthropic", families)
        self.assertTrue(any("authoring family" in p for p in problems))

    def test_anthropic_alone_leaves_the_panel_empty(self):
        families, _, problems = self.seats({"ANTHROPIC_API_KEY": "a"})
        self.assertEqual(families, [])
        self.assertTrue(problems)

    def test_empty_values_do_not_count(self):
        families, _, _ = self.seats({"GEMINI_API_KEY": "", "MOONSHOT_API_KEY": "x"})
        self.assertEqual(families, ["moonshot"])

    def test_unknown_keys_are_ignored(self):
        families, _, _ = self.seats({"SOME_OTHER_TOKEN": "x", "MOONSHOT_API_KEY": "y"})
        self.assertEqual(families, ["moonshot"])

    def test_shortfall_names_the_requirement(self):
        _, _, problems = self.seats({"MOONSHOT_API_KEY": "a"})
        self.assertTrue(any(str(doctor.SEATS_REQUIRED) in p for p in problems))

    def test_paste_seats_fill_the_panel_without_keys(self):
        families, notes, problems = self.seats({
            doctor.PASTE_SEATS_KEY: "google, moonshot,openai"})
        self.assertEqual(sorted(families), ["google", "moonshot", "openai"])
        self.assertEqual(problems, [])
        self.assertTrue(any("paste" in n for n in notes))

    def test_a_paste_seat_does_not_duplicate_a_key(self):
        families, notes, _ = self.seats({
            "GEMINI_API_KEY": "a", doctor.PASTE_SEATS_KEY: "google"})
        self.assertEqual(families, ["google"])
        self.assertTrue(any("duplicates" in n for n in notes))

    def test_anthropic_cannot_be_a_paste_seat(self):
        families, _, problems = self.seats({
            doctor.PASTE_SEATS_KEY: "anthropic,google,moonshot"})
        self.assertNotIn("anthropic", families)
        self.assertTrue(any("authoring family" in p for p in problems))

    def test_an_unknown_paste_family_is_reported(self):
        _, _, problems = self.seats({doctor.PASTE_SEATS_KEY: "acme"})
        self.assertTrue(any("unknown family" in p for p in problems))


class CheckStatusTest(unittest.TestCase):
    def test_required_failure_is_fail_and_optional_is_warn(self):
        self.assertEqual(doctor.Check("x", False, "", required=True).status, "FAIL")
        self.assertEqual(doctor.Check("x", False, "", required=False).status, "warn")
        self.assertEqual(doctor.Check("x", True, "").status, "pass")


class RenderTest(unittest.TestCase):
    def test_a_required_failure_is_surfaced_with_its_fix(self):
        out = doctor.render([
            doctor.Check("Thing", False, "broken", required=True, fix="do-the-thing"),
            doctor.Check("Other", True, "fine"),
        ])
        self.assertIn("[FAIL]", out)
        self.assertIn("do-the-thing", out)
        self.assertIn("1 required check(s) failed", out)

    def test_all_passing_points_at_the_next_step(self):
        out = doctor.render([doctor.Check("Thing", True, "fine")])
        self.assertIn("All required checks passed", out)
        self.assertIn("/ideate", out)

    def test_optional_failures_do_not_claim_a_required_failure(self):
        out = doctor.render([
            doctor.Check("Thing", True, "fine"),
            doctor.Check("Optional", False, "missing", required=False),
        ])
        self.assertIn("All required checks passed", out)
        self.assertIn("Optional, not blocking", out)


if __name__ == "__main__":
    unittest.main()


class EnvironmentBlockersTest(unittest.TestCase):
    """Phase-aware environment preconditions. The design point: a phase must not pay for a
    check it does not need, and a problem that bites later must be surfaced early."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "cache.json"
        self._saved = doctor.CACHE
        doctor.CACHE = self.cache
        self.addCleanup(lambda: setattr(doctor, "CACHE", self._saved))
        self.addCleanup(self.tmp.cleanup)

    def seed(self, name, ok, detail="d", fix="f", age=0.0):
        import json as _json, time as _time
        self.cache.write_text(_json.dumps({
            "checked_at": _time.time() - age,
            "checks": [{"name": name, "ok": ok, "required": False,
                        "detail": detail, "fix": fix}]}))

    def test_early_phases_require_nothing(self):
        for phase in ("ideate", "proposal", "design"):
            with self.subTest(phase=phase):
                self.assertEqual(doctor.PHASE_REQUIREMENTS.get(phase, ()), ())

    def test_handover_requires_the_panel(self):
        self.assertIn("panel", doctor.PHASE_REQUIREMENTS["handover"])

    def test_build_phases_require_git_identity(self):
        for phase in ("build", "devops", "launch"):
            with self.subTest(phase=phase):
                self.assertIn("git", doctor.PHASE_REQUIREMENTS[phase])

    def test_a_failing_panel_blocks_handover(self):
        self.seed("Judge panel", ok=False, detail="1/3 seats", fix="add a key")
        blockers, _ = doctor.environment_blockers("handover")
        self.assertTrue(blockers)
        self.assertIn("1/3 seats", blockers[0])
        self.assertIn("add a key", blockers[0])

    def test_a_passing_panel_does_not_block_handover(self):
        self.seed("Judge panel", ok=True, detail="3/3 seats")
        blockers, _ = doctor.environment_blockers("handover")
        self.assertEqual(blockers, [])

    def test_a_failing_panel_only_advises_during_early_phases(self):
        self.seed("Judge panel", ok=False, detail="1/3 seats")
        blockers, advisories = doctor.environment_blockers("ideate")
        self.assertEqual(blockers, [])
        self.assertTrue(advisories)
        self.assertIn("/handover will refuse", advisories[0])

    def test_no_advisory_when_the_panel_is_fine(self):
        self.seed("Judge panel", ok=True, detail="3/3 seats")
        _, advisories = doctor.environment_blockers("ideate")
        self.assertEqual(advisories, [])

    def test_a_stale_cache_is_ignored(self):
        self.seed("Judge panel", ok=False, detail="stale", age=doctor.CACHE_TTL_SECONDS + 60)
        _, advisories = doctor.environment_blockers("ideate")
        self.assertEqual(advisories, [], "a stale cache must not drive an advisory")

    def test_a_corrupt_cache_is_ignored_rather_than_raising(self):
        self.cache.write_text("{ not json")
        blockers, advisories = doctor.environment_blockers("ideate")
        self.assertEqual((blockers, advisories), ([], []))

    def test_cache_write_round_trips(self):
        doctor.cache_write([doctor.Check("Judge panel", False, "1/3", required=False, fix="x")])
        _, advisories = doctor.environment_blockers("ideate")
        self.assertTrue(advisories)
