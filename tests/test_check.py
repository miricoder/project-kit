"""Tests for the local CI runner.

The point of `pk check` is that it runs what CI runs. If the two drift, the command is
worse than useless — it gives false confidence. So the commands are pinned against the
workflow file itself.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check  # noqa: E402
import doctor  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class ParityWithCiTest(unittest.TestCase):
    """The commands here must match .github/workflows/ci.yml. Change one, change both."""

    def setUp(self):
        self.workflow = WORKFLOW.read_text()
        self.run_lines = [m.group(1).strip() for m in
                          re.finditer(r"^\s*run:\s*(.+)$", self.workflow, re.M)]

    def test_the_workflow_still_exists(self):
        self.assertTrue(WORKFLOW.is_file(), "ci.yml moved; update this test and check.py")

    def test_unittest_discovery_matches(self):
        local = " ".join(check.TEST_COMMAND[1:])          # drop the interpreter path
        self.assertTrue(
            any("unittest discover -s tests -t ." in line for line in self.run_lines),
            "CI no longer runs unittest discovery the way check.py does")
        self.assertIn("unittest discover -s tests -t .", local)

    def test_docs_staleness_gate_matches(self):
        self.assertTrue(
            any("build_docs.py --check" in line for line in self.run_lines),
            "CI no longer runs the docs staleness gate")
        self.assertIn("--check", check.DOCS_COMMAND)

    def test_plugin_validate_matches(self):
        self.assertTrue(
            any("plugin validate" in line and "--strict" in line for line in self.run_lines),
            "CI no longer runs plugin validate --strict")

    def test_every_ci_step_has_a_local_counterpart(self):
        """A new CI step with no local equivalent means `pk check` passing proves less than
        the user thinks."""
        meaningful = [line for line in self.run_lines
                      if not line.startswith("npm i") and "setup" not in line]
        covered = ("unittest", "build_docs", "plugin validate")
        uncovered = [line for line in meaningful
                     if not any(token in line for token in covered)]
        self.assertEqual(uncovered, [], f"CI steps with no local counterpart: {uncovered}")


class CollectTest(unittest.TestCase):
    """collect() shells out to `unittest discover`, which would re-run this very file and
    recurse. Every subprocess is stubbed; what is under test is order and shape."""

    def setUp(self):
        self._run, self._which = check.run, check.shutil.which
        check.run = lambda argv, timeout=20.0: (0, "Ran 1 test in 0.001s\n\nOK")
        check.shutil.which = lambda name: "/fake/claude"
        self.addCleanup(lambda: setattr(check, "run", self._run))
        self.addCleanup(lambda: setattr(check.shutil, "which", self._which))

    def test_runs_three_checks_in_ci_order(self):
        names = [c.name for c in check.collect()]
        self.assertEqual(names, ["Unit tests", "Docs up to date", "Plugin manifests"])

    def test_checks_are_the_shared_dataclass(self):
        for item in check.collect():
            self.assertIsInstance(item, doctor.Check)

    def test_all_passing_subprocesses_give_a_clean_run(self):
        self.assertTrue(all(c.ok for c in check.collect()))


class PluginValidateDegradationTest(unittest.TestCase):
    """On a machine with no Claude Code, the command must still be usable."""

    def setUp(self):
        self._which = check.shutil.which
        self.addCleanup(lambda: setattr(check.shutil, "which", self._which))

    def test_missing_cli_warns_rather_than_fails(self):
        check.shutil.which = lambda name: None
        result = check.validate_plugin()
        self.assertFalse(result.ok)
        self.assertFalse(result.required, "a missing CLI must not fail the whole run")
        self.assertEqual(result.status, "warn")

    def test_an_old_cli_without_the_plugin_command_also_warns(self):
        check.shutil.which = lambda name: "/fake/claude"
        real_run = check.run
        check.run = lambda argv, timeout=20.0: (1, "Usage: claude [options] [command]")
        self.addCleanup(lambda: setattr(check, "run", real_run))
        result = check.validate_plugin()
        self.assertFalse(result.required)
        self.assertIn("no `plugin` command", result.detail)


class ExitCodeTest(unittest.TestCase):
    def test_required_failure_exits_1(self):
        real = check.collect
        check.collect = lambda fix=False: [doctor.Check("X", False, "broken", required=True)]
        self.addCleanup(lambda: setattr(check, "collect", real))
        self.assertEqual(check.main([]), 1)

    def test_optional_failure_alone_exits_0(self):
        real = check.collect
        check.collect = lambda fix=False: [
            doctor.Check("X", True, "fine"),
            doctor.Check("Y", False, "skipped", required=False)]
        self.addCleanup(lambda: setattr(check, "collect", real))
        self.assertEqual(check.main([]), 0)


class RenderReuseTest(unittest.TestCase):
    def test_check_supplies_its_own_title_and_closing_line(self):
        out = doctor.render([doctor.Check("X", True, "fine")],
                            title="Project Kit — repository checks (same as CI)",
                            success="Safe to commit and push.")
        self.assertIn("repository checks", out)
        self.assertIn("Safe to commit and push.", out)
        self.assertNotIn("/ideate", out, "the environment-check footer must not leak in")

    def test_doctor_keeps_its_own_defaults(self):
        out = doctor.render([doctor.Check("X", True, "fine")])
        self.assertIn("environment check", out)
        self.assertIn("/ideate", out)


if __name__ == "__main__":
    unittest.main()
