"""Tests for skills/build/scripts/slices.py: the mechanical half of /build.

The important ones are the refusals: a slice is never recorded done while a scenario is
unmapped or the test command fails, whatever the model believes.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "build" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "pipeline" / "scripts"))

import slices  # noqa: E402
import state  # noqa: E402

FEATURE = """Feature: Things

  Scenario: a task is filed with its day
    Given a capture
    Then a task exists

  Scenario: an expense is filed
    Given a capture
    Then an expense exists

  Scenario: undo restores the previous state
    Given a change
    Then it is undone
"""

BACKLOG = """# Backlog: demo

## Slice 1: Filing
- **Delivers:** captures become tasks and expenses
- **Scenarios:** a task is filed with its day; an expense
  is filed
- **Touches:** service
- **Done when:** its scenarios pass as automated tests

## Slice 2: Undo
- **Delivers:** undo
- **Scenarios:** undo restores the previous state
- **Done when:** its scenarios pass as automated tests
"""

PASS = f'"{sys.executable}" -c "raise SystemExit(0)"'
FAIL = f'"{sys.executable}" -c "raise SystemExit(3)"'


class SliceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        os.environ["PROJECT_KIT_REGISTRY"] = str(self.dir / "registry.json")
        self.addCleanup(os.environ.pop, "PROJECT_KIT_REGISTRY", None)
        (self.dir / "docs").mkdir()
        (self.dir / "docs" / "acceptance.feature").write_text(FEATURE)
        (self.dir / "docs" / "backlog.md").write_text(BACKLOG)
        st = state.new_state("demo")
        for phase in state.PHASES[:6]:
            st["phases"][phase]["status"] = "complete"
        state.save(st, self.dir)

    def run_cli(self, *args):
        import contextlib
        import io
        o, e = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            code = slices.main(["-C", str(self.dir), *args])
        return code, o.getvalue(), e.getvalue()

    def write_test(self, *scenario_names):
        tests = self.dir / "tests"
        tests.mkdir(exist_ok=True)
        body = "\n".join(f'def test_{i}():\n    """Scenario: {n}"""\n'
                         for i, n in enumerate(scenario_names))
        (tests / "test_demo.py").write_text(body)

    # ---- parsing ---------------------------------------------------------------------

    def test_backlog_slices_and_their_scenarios_are_parsed(self):
        parsed = slices.parse_backlog(self.dir)
        self.assertEqual([s["number"] for s in parsed], [1, 2])
        self.assertEqual(parsed[0]["name"], "Filing")
        self.assertEqual(parsed[0]["scenarios"],
                         ["a task is filed with its day", "an expense is filed"],
                         "a scenario name wrapped over two lines still belongs to its slice")
        self.assertEqual(parsed[1]["scenarios"], ["undo restores the previous state"])
        self.assertEqual(parsed[0]["delivers"], "captures become tasks and expenses")

    def test_missing_backlog_is_an_error_not_a_crash(self):
        (self.dir / "docs" / "backlog.md").unlink()
        code, _, err = self.run_cli("list")
        self.assertEqual(code, 2)
        self.assertIn("run /initiate first", err)

    # ---- start ---------------------------------------------------------------------

    def test_next_names_the_first_unfinished_slice(self):
        code, out, _ = self.run_cli("next")
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(data["slice"]["number"], 1)
        self.assertTrue(data["runnable"])

    def test_start_is_refused_until_initiate_is_complete(self):
        st = state.load(self.dir)
        st["phases"]["initiate"]["status"] = "in progress"
        state.save(st, self.dir)
        code, _, err = self.run_cli("start", "1")
        self.assertEqual(code, 1)
        self.assertIn("initiate is in progress", err)

    def test_start_marks_slice_and_build_phase_in_progress(self):
        code, _, _ = self.run_cli("start", "1")
        self.assertEqual(code, 0)
        st = state.load(self.dir)
        self.assertEqual(st["slices"]["1"]["status"], "in progress")
        self.assertEqual(st["phases"]["build"]["status"], "in progress")

    # ---- done: the refusals ----------------------------------------------------------

    def test_done_refuses_a_slice_that_was_never_started(self):
        self.write_test("a task is filed with its day", "an expense is filed")
        self.run_cli("config", "--test-command", PASS)
        code, _, err = self.run_cli("done", "1")
        self.assertEqual(code, 1)
        self.assertIn("never started", err)

    def test_done_refuses_an_unmapped_scenario(self):
        self.write_test("a task is filed with its day")
        self.run_cli("config", "--test-command", PASS)
        self.run_cli("start", "1")
        code, _, err = self.run_cli("done", "1")
        self.assertEqual(code, 1)
        self.assertIn("scenario not named in any test: 'an expense is filed'", err)
        self.assertEqual(state.load(self.dir)["slices"]["1"]["status"], "in progress")

    def test_done_refuses_when_the_tests_fail(self):
        self.write_test("a task is filed with its day", "an expense is filed")
        self.run_cli("config", "--test-command", FAIL)
        self.run_cli("start", "1")
        code, _, err = self.run_cli("done", "1")
        self.assertEqual(code, 1)
        self.assertIn("test command failed (exit 3)", err)

    def test_done_refuses_without_a_test_command(self):
        self.write_test("a task is filed with its day", "an expense is filed")
        self.run_cli("start", "1")
        code, _, err = self.run_cli("done", "1")
        self.assertEqual(code, 1)
        self.assertIn("no test command recorded", err)

    def test_done_refuses_without_any_tests(self):
        self.run_cli("config", "--test-command", PASS)
        self.run_cli("start", "1")
        code, _, err = self.run_cli("done", "1")
        self.assertEqual(code, 1)
        self.assertIn("no test files", err)

    # ---- done: success ---------------------------------------------------------------

    def test_done_records_the_slice_and_names_the_next(self):
        self.write_test("a task is filed with its day", "an expense is filed")
        self.run_cli("config", "--test-command", PASS)
        self.run_cli("start", "1")
        code, out, _ = self.run_cli("done", "1")
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(data["slice"]["status"], "complete")
        self.assertFalse(data["build_complete"])
        self.assertEqual(data["next_slice"]["number"], 2)

    def test_the_last_slice_completes_the_build_phase(self):
        self.write_test("a task is filed with its day", "an expense is filed",
                        "undo restores the previous state")
        self.run_cli("config", "--test-command", PASS)
        for n in ("1", "2"):
            self.run_cli("start", n)
            self.assertEqual(self.run_cli("done", n)[0], 0)
        st = state.load(self.dir)
        self.assertEqual(st["phases"]["build"]["status"], "complete")
        self.assertEqual(state.next_phase(st), "devops")

    def test_scenario_matching_ignores_case_and_spacing(self):
        self.write_test("A task is   filed with its DAY", "an expense is filed")
        self.run_cli("config", "--test-command", PASS)
        self.run_cli("start", "1")
        self.assertEqual(self.run_cli("check", "1")[0], 0)

    def test_block_records_the_reason(self):
        code, out, _ = self.run_cli("block", "2", "--reason", "needs an API key")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["slice"]["blocked_reason"], "needs an API key")

    def test_older_state_without_slice_keys_still_loads(self):
        st = json.loads((self.dir / "pipeline.json").read_text())
        self.assertNotIn("slices", st)
        code, out, _ = self.run_cli("list")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["complete"], 0)


if __name__ == "__main__":
    unittest.main()
