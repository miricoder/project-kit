"""Tests for bin/pk, the launcher every skill invokes.

Two failures shipped here and both were found by a user, not by tests:
  - skills referenced "$CLAUDE_PLUGIN_ROOT/bin/pk", but that variable is not exported into
    the shell environment, so it expanded to "/bin/pk"
  - the launcher derived its root from $0 without following symlinks, so invoking it
    through ~/.local/bin/pk looked for scripts in ~/.local/
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PK = ROOT / "bin" / "pk"
SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))


class LauncherResolutionTest(unittest.TestCase):
    def run_pk(self, executable: Path, *args, env=None):
        return subprocess.run([str(executable), *args], capture_output=True, text=True,
                              env={**os.environ, **(env or {})}, timeout=60)

    def test_runs_when_invoked_directly(self):
        result = self.run_pk(PK, "gate", "harness")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unattended_ready", result.stdout)

    def test_runs_when_invoked_through_a_symlink(self):
        """`setup.sh --fix` links pk into ~/.local/bin; taking dirname of the link pointed
        at the link's own directory instead of the plugin."""
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / "pk"
            link.symlink_to(PK)
            result = self.run_pk(link, "gate", "harness")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("not found; set PROJECT_KIT_ROOT", result.stderr)

    def test_runs_through_a_chain_of_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "pk-one"
            second = Path(tmp) / "pk-two"
            first.symlink_to(PK)
            second.symlink_to(first)
            self.assertEqual(self.run_pk(second, "gate", "harness").returncode, 0)

    def test_explicit_root_still_wins(self):
        result = self.run_pk(PK, "gate", "harness", env={"PROJECT_KIT_ROOT": str(ROOT)})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_judge_subcommand_resolves(self):
        result = self.run_pk(PK, "judge", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("combine", result.stdout)

    def test_qa_subcommand_resolves(self):
        result = self.run_pk(PK, "qa", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("backlog", result.stdout)

    def test_powershell_launcher_knows_every_subcommand(self):
        """The two launchers must agree, or a Windows user hits a ValidateSet error."""
        ps1 = (ROOT / "bin" / "pk.ps1").read_text()
        for sub in ("state", "gate", "doctor", "check", "judge", "qa"):
            self.assertIn(f"'{sub}'", ps1)

    def test_unknown_subcommand_is_a_usage_error(self):
        self.assertEqual(self.run_pk(PK, "nonsense").returncode, 2)


class SkillCommandFormTest(unittest.TestCase):
    """The skills must not depend on an environment variable the runtime does not set."""

    def test_no_skill_dereferences_claude_plugin_root_in_a_command(self):
        offenders = []
        for path in SKILLS:
            for line in path.read_text().splitlines():
                stripped = line.strip()
                # a command line, not prose explaining the variable
                if stripped.startswith(("pk ", '"$CLAUDE_PLUGIN_ROOT', "$CLAUDE_PLUGIN_ROOT")) \
                        and "CLAUDE_PLUGIN_ROOT" in stripped:
                    offenders.append(f"{path.parent.name}: {stripped}")
        self.assertEqual(offenders, [],
                         "skills must resolve the launcher by path, not via "
                         "$CLAUDE_PLUGIN_ROOT, which is not exported into the shell")

    def test_every_skill_documents_how_to_resolve_the_launcher(self):
        for path in SKILLS:
            with self.subTest(skill=path.parent.name):
                text = path.read_text()
                self.assertIn("command -v pk", text,
                              "each skill must show how to find the launcher")
                self.assertTrue(
                    re.search(r"plugins/cache/project-kit", text),
                    "the resolver must cover a marketplace install")


if __name__ == "__main__":
    unittest.main()
