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
