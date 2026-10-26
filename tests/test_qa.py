"""Tests for scripts/qa.py: the checks /remediate loops on, and the hook that re-runs them.

The browser scan itself needs node and playwright, which CI does not have; everything that
decides pass or fail (lint, backlog coverage, flattening, evaluating a scan) is pure and
tested here.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "pipeline" / "scripts"))

import qa  # noqa: E402
import state  # noqa: E402

SPEC = """# Technical spec: demo

## Architecture

One app, one local store.

## Decisions

| Decision | Chosen | Rejected | Why |
|---|---|---|---|
| Store | SQLite | Files | Queries |

## Data model

| Entity | Fields | Lives in |
|---|---|---|
| Expense | amount, date | SQLite |

## Interfaces

`file(text) -> items`

## Failure modes

| What goes wrong | System does | Scenario |
|---|---|---|
| Offline | Queues the capture | Capture while offline |

## Rollback

| Layer | How | Tested by |
|---|---|---|
| Code | Redeploy the previous tag | release drill |
| Data | Reverse migration | migration test |

## Security and privacy

| Concern | Handling |
|---|---|
| Sensitive data | Encrypted at rest |

## Not built

Bank sync.

## Strongest counter-argument

Filing accuracy has never been measured on real captures.
"""

FEATURE = """Feature: capture
  Scenario: File an expense
    Given the app is open
    When I type "paid 42 for groceries"
    Then an expense of 42 is filed

  Scenario: Capture while offline
    Given there is no connection
    When I type "taxi 18"
    Then it is shown as waiting to file
"""


class ProjectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        (self.project / "docs").mkdir()
        self.write("docs/spec.md", SPEC)
        self.write("docs/acceptance.feature", FEATURE)

    def write(self, rel, text):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def details(self, problems):
        return " | ".join(p["detail"] for p in problems)


class LintTest(ProjectTest):
    def test_a_complete_plan_passes(self):
        self.assertEqual(qa.lint(self.project), [])

    def test_a_missing_section_fails(self):
        self.write("docs/spec.md", SPEC.replace("## Interfaces\n\n`file(text) -> items`\n", ""))
        self.assertIn("'## Interfaces' is missing", self.details(qa.lint(self.project)))

    def test_a_placeholder_section_fails(self):
        self.write("docs/spec.md", SPEC.replace("Bank sync.", "<Explicitly out of scope>"))
        self.assertIn("'## Not built' is empty or a placeholder",
                      self.details(qa.lint(self.project)))

    def test_a_table_with_only_its_header_is_a_placeholder(self):
        self.write("docs/spec.md", SPEC.replace("| Sensitive data | Encrypted at rest |\n", ""))
        self.assertIn("'## Security and privacy' is empty or a placeholder",
                      self.details(qa.lint(self.project)))

    def test_a_failure_mode_must_point_at_a_real_scenario(self):
        self.write("docs/spec.md", SPEC.replace("| Capture while offline |", "| Lost phone |"))
        self.assertIn("'Lost phone', which is not in", self.details(qa.lint(self.project)))
        self.write("docs/spec.md", SPEC.replace("| Capture while offline |", "| |"))
        self.assertIn("names no scenario", self.details(qa.lint(self.project)))

    def test_a_decision_needs_its_rejected_alternative(self):
        self.write("docs/spec.md", SPEC.replace("| Store | SQLite | Files |", "| Store | SQLite | |"))
        self.assertIn("names no rejected alternative", self.details(qa.lint(self.project)))

    def test_rollback_must_cover_data(self):
        self.write("docs/spec.md", SPEC.replace("| Data | Reverse migration |", "| Data | |"))
        self.assertIn("no rollback stated for data", self.details(qa.lint(self.project)))

    def test_a_scenario_needs_an_outcome(self):
        self.write("docs/acceptance.feature",
                   FEATURE.replace("    Then an expense of 42 is filed\n", ""))
        self.assertIn("'File an expense' has no Then", self.details(qa.lint(self.project)))

    def test_missing_documents_fail(self):
        (self.project / "docs/acceptance.feature").unlink()
        self.assertIn("missing", self.details(qa.lint(self.project)))

    def test_sections_match_the_design_template(self):
        template = (ROOT / "skills/design/references/spec-template.md").read_text()
        headings = [line[3:].strip() for line in template.splitlines()
                    if line.startswith("## ")]
        self.assertEqual(tuple(headings), qa.SPEC_SECTIONS)


class BacklogTest(ProjectTest):
    def test_every_scenario_must_be_in_a_slice(self):
        self.write("docs/backlog.md", "# Backlog\n\n## Slice 1: capture\n- File an expense\n")
        self.assertIn("'Capture while offline' is in no slice",
                      self.details(qa.backlog(self.project)))
        self.write("docs/backlog.md", "# Backlog\n\n## Slice 1: capture\n- File an expense\n"
                                      "- Capture while offline\n")
        self.assertEqual(qa.backlog(self.project), [])

    def test_slices_are_required(self):
        self.write("docs/backlog.md", "File an expense. Capture while offline.")
        self.assertIn("no '## Slice", self.details(qa.backlog(self.project)))


ARTBOARD = """<!doctype html>
<html lang="pt">
<head><title>Home</title><script src="./support.js"></script></head>
<body>
<x-dc>
<helmet><link href="x"><style>.a{color:red}</style></helmet>
<main><button style="background: {{accent}}">Go</button><input type="checkbox" defaultChecked="{{ true }}"></main>
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{"accent":{"editor":"color","default":"#123456"}}'>
class Component extends DCLogic {}
</script>
</body>
</html>"""


class A11yTest(ProjectTest):
    def test_flatten_produces_plain_html(self):
        html = qa.flatten(ARTBOARD)
        self.assertIn('<html lang="pt">', html)
        self.assertIn("<style>.a{color:red}</style>", html)
        self.assertIn("background: #123456", html)
        self.assertIn('<input type="checkbox" checked>', html)
        self.assertNotIn("{{", html)
        self.assertNotIn("DCLogic", html)

    def test_plain_html_is_left_alone(self):
        self.assertEqual(qa.flatten("<html><body>x</body></html>"), "<html><body>x</body></html>")

    def test_ui_files_are_found_and_judging_output_is_not(self):
        self.write("ui/home.html", "<html></html>")
        self.write("mockups/Main.dc.html", ARTBOARD)
        self.write("judge/round-1/brief.html", "<html></html>")
        self.write("docs/notes.html", "<html></html>")
        found = sorted(str(p.relative_to(self.project)) for p in qa.ui_files(self.project))
        self.assertEqual(found, ["mockups/Main.dc.html", "ui/home.html"])

    def test_evaluate_turns_a_scan_into_problems(self):
        problems = qa.evaluate([
            {"file": "ui/a.html", "violations": [{"id": "color-contrast", "impact": "serious",
                                                   "help": "Contrast", "targets": ["p"]}],
             "focusMissing": ["Send"], "overflow320": True},
            {"file": "ui/b.html", "violations": [], "focusMissing": [], "overflow320": False},
        ])
        text = self.details(problems)
        self.assertIn("ui/a.html: color-contrast (serious)", text)
        self.assertIn("no visible focus on 'Send'", text)
        self.assertIn("scrolls sideways at 320px", text)
        self.assertNotIn("ui/b.html", text)

    def test_no_ui_files_means_nothing_to_scan(self):
        self.assertEqual(qa.a11y(self.project), [])

    def test_an_unusable_scanner_fails_rather_than_passing_silently(self):
        self.write("ui/home.html", "<html></html>")
        with mock.patch.object(qa, "scanner_ready", lambda: "node is not installed"):
            self.assertIn("not scanned: node is not installed",
                          self.details(qa.a11y(self.project)))


class HookTest(ProjectTest):
    def run_hook(self, payload):
        err = io.StringIO()
        with redirect_stderr(err):
            code = qa.hook(json.dumps(payload))
        return code, err.getvalue()

    def test_files_outside_a_project_are_ignored(self):
        other = Path(self.tmp.name) / "elsewhere"
        other.mkdir()
        page = other / "page.html"
        page.write_text("<html></html>")
        with mock.patch.object(qa, "a11y", side_effect=AssertionError("must not scan")):
            self.assertEqual(self.run_hook({"tool_input": {"file_path": str(page)}})[0], 0)

    def test_non_ui_files_and_bad_input_are_ignored(self):
        state.save(state.new_state("demo"), self.project)
        with mock.patch.object(qa, "a11y", side_effect=AssertionError("must not scan")):
            for payload in ({"tool_input": {"file_path": str(self.project / "docs/spec.md")}},
                            {"tool_input": {}}, {}):
                self.assertEqual(self.run_hook(payload)[0], 0)
            self.assertEqual(qa.hook("not json"), 0)

    def test_a_failing_ui_file_is_handed_back(self):
        state.save(state.new_state("demo"), self.project)
        page = self.write("ui/home.html", "<html></html>")
        found = [{"check": "a11y", "detail": "ui/home.html: button-name (critical)"}]
        with mock.patch.object(qa, "a11y", return_value=found):
            code, err = self.run_hook({"tool_input": {"file_path": str(page)}})
        self.assertEqual(code, 2)
        self.assertIn("button-name", err)

    def test_a_passing_ui_file_is_silent(self):
        state.save(state.new_state("demo"), self.project)
        page = self.write("ui/home.html", "<html></html>")
        with mock.patch.object(qa, "a11y", return_value=[]):
            self.assertEqual(self.run_hook({"tool_input": {"file_path": str(page)}}), (0, ""))

    def test_the_plugin_registers_the_hook(self):
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
        commands = [h["command"] for entry in hooks["PostToolUse"] for h in entry["hooks"]]
        self.assertTrue(any("qa hook" in c and "CLAUDE_PLUGIN_ROOT" in c for c in commands))


class ReportTest(ProjectTest):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {
            "PROJECT_KIT_REGISTRY": str(Path(self.tmp.name) / "registry.json")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = qa.main(["-C", str(self.project), *args])
        return code, json.loads(out.getvalue())

    def test_everything_passes_only_with_the_judge_gate_open(self):
        st = state.new_state("demo")
        state.save(st, self.project)
        code, report = self.run_main()
        self.assertEqual(code, 1)
        self.assertFalse(report["checks"]["judge"]["passed"])
        self.assertTrue(report["checks"]["lint"]["passed"])
        state.record_ruling(st, "judge", "SOUND", 1, [])
        state.save(st, self.project)
        code, report = self.run_main()
        self.assertEqual(code, 0)
        self.assertTrue(report["passed"])
        self.assertTrue((self.project / "qa" / "report.json").is_file())

    def test_open_fixes_are_reported(self):
        st = state.new_state("demo")
        state.record_ruling(st, "judge", "FIX FIRST", 1, ["google-1: x", "xai-1: y"])
        state.save(st, self.project)
        problems = qa.judge_status(self.project)
        self.assertIn("FIX FIRST, 2 fix(es) open", problems[0]["detail"])


if __name__ == "__main__":
    unittest.main()
