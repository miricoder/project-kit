"""Tests for gate.py — the refusal mechanism.

Exit codes are the contract a skill relies on, so they are asserted through a real
subprocess rather than by calling into the module.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "pipeline" / "scripts"
GATE = SCRIPTS / "gate.py"
sys.path.insert(0, str(SCRIPTS))

import gate  # noqa: E402
import state  # noqa: E402


class GateCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.env = {**os.environ,
                    "PROJECT_KIT_REGISTRY": str(self.dir / "registry.json")}

    def write(self, st):
        state.save(st, self.dir)

    def run_gate(self, *args):
        return subprocess.run([sys.executable, str(GATE), "-C", str(self.dir), *args],
                              capture_output=True, text=True, env=self.env)

    def fresh(self, **kw):
        return state.new_state("demo", **kw)

    # ---- exit codes

    def test_missing_state_file_exits_2(self):
        result = self.run_gate("phase", "ideate")
        self.assertEqual(result.returncode, 2)
        self.assertIn("/pipeline init", result.stderr)

    def test_runnable_phase_exits_0(self):
        self.write(self.fresh())
        result = self.run_gate("phase", "ideate")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["runnable"])

    def test_phase_with_incomplete_predecessor_exits_1_and_says_why(self):
        self.write(self.fresh())
        result = self.run_gate("phase", "design")
        self.assertEqual(result.returncode, 1)
        self.assertIn("REFUSED", result.stderr)
        self.assertIn("ideate", result.stderr)

    def test_initiate_is_refused_until_the_judge_gate_passes(self):
        st = self.fresh()
        for phase in state.WAVE1:
            state.set_phase(st, phase, "complete")
        self.write(st)
        refused = self.run_gate("phase", "initiate")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("judge gate has not passed", refused.stderr)

        state.record_ruling(st, "judge", "SOUND", 1)
        self.write(st)
        self.assertEqual(self.run_gate("phase", "initiate").returncode, 0)

    def test_gate_subcommand_refuses_and_lists_open_fixes(self):
        st = self.fresh()
        state.record_ruling(st, "judge", "FIX FIRST", 1, ["add a migration", "cap retries"])
        self.write(st)
        result = self.run_gate("gate", "judge")
        self.assertEqual(result.returncode, 1)
        self.assertIn("add a migration", result.stderr)
        self.assertIn("cap retries", result.stderr)

    def test_gate_subcommand_passes_on_sound(self):
        st = self.fresh()
        state.record_ruling(st, "judge", "SOUND", 1)
        self.write(st)
        result = self.run_gate("gate", "judge")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["ruling"], "SOUND")

    def test_unknown_phase_is_a_usage_error(self):
        self.write(self.fresh())
        self.assertEqual(self.run_gate("phase", "nonsense").returncode, 2)


class AllowlistTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "settings.json"
        self.addCleanup(self.tmp.cleanup)
        self._saved = gate.SETTINGS
        gate.SETTINGS = self.path
        self.addCleanup(lambda: setattr(gate, "SETTINGS", self._saved))

    def test_absent_settings_reports_every_permission_missing(self):
        self.assertEqual(gate.allowlist_gaps(), list(gate.NEEDED_PERMISSIONS))

    def test_malformed_settings_is_treated_as_not_configured(self):
        self.path.write_text("{ this is not json")
        self.assertEqual(gate.allowlist_gaps(), list(gate.NEEDED_PERMISSIONS))

    def test_scoped_bash_rule_satisfies_the_bash_requirement(self):
        self.path.write_text(json.dumps({"permissions": {"allow": ["Bash(git:*)"]}}))
        self.assertNotIn("Bash", gate.allowlist_gaps())

    def test_a_full_allowlist_reports_ready(self):
        self.path.write_text(json.dumps(
            {"permissions": {"allow": ["Bash(python3:*)", "Edit", "Write"]}}))
        self.assertEqual(gate.allowlist_gaps(), [])


if __name__ == "__main__":
    unittest.main()
