"""Tests for scripts/keys.py, which stores judge keys and fills the panel.

A key that leaks into a repository is the failure this module exists to prevent, so the
tests check where it is written, with what permissions, and that it is never printed.
"""
from __future__ import annotations

import io
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import doctor  # noqa: E402
import keys  # noqa: E402

KEY = "sk-test-0123456789abcdefXYZ"
PANEL_VARS = [k for k in os.environ
              if k in doctor.FAMILY_BY_KEY or k == doctor.PASTE_SEATS_KEY]


class KeysTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home = Path(self.tmp.name) / "project-kit"
        for name, value in (("ENV_FILE", home / ".env"), ("CACHE", home / "environment.json")):
            patcher = mock.patch.object(doctor, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        env = mock.patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        for name in PANEL_VARS:
            os.environ.pop(name, None)
        which = mock.patch.object(doctor.shutil, "which",
                                  side_effect=lambda name: None)  # no codex CLI
        which.start()
        self.addCleanup(which.stop)

    def run_keys(self, *argv, stdin=""):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(stdin)), \
                redirect_stdout(out), redirect_stderr(err):
            code = keys.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_an_empty_panel_asks_for_at_least_one_key(self):
        code, out, _ = self.run_keys("status")
        report = json.loads(out)
        self.assertEqual(code, 1)
        self.assertFalse(report["ready"])
        self.assertFalse(report["has_key_seat"])
        self.assertIn("at least one judge key", report["ask"])

    def test_add_stores_the_key_privately_and_never_prints_it(self):
        code, out, err = self.run_keys("add", "openai", "--stdin", stdin=KEY + "\n")
        self.assertEqual(code, 0, err)
        self.assertNotIn(KEY, out + err)
        path = doctor.ENV_FILE
        self.assertIn(f"OPENAI_API_KEY={KEY}", path.read_text())
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertEqual(json.loads(out)["panel"]["key_seats"], ["openai"])

    def test_add_replaces_an_existing_key_and_keeps_other_lines(self):
        doctor.ENV_FILE.parent.mkdir(parents=True)
        doctor.ENV_FILE.write_text("# mine\nOPENAI_API_KEY=old-old-old-old-old\n"
                                   "GEMINI_API_KEY=gggggggggggggggggggg\n")
        self.run_keys("add", "openai", "--stdin", stdin=KEY)
        text = doctor.ENV_FILE.read_text()
        self.assertEqual(text.count("OPENAI_API_KEY="), 1)
        self.assertNotIn("old-old", text)
        self.assertIn("# mine", text)
        self.assertIn("GEMINI_API_KEY=", text)

    def test_anthropic_cannot_be_added(self):
        code, _, err = self.run_keys("add", "anthropic", "--stdin", stdin=KEY)
        self.assertEqual(code, 1)
        self.assertIn("cannot hold a judge seat", err)
        self.assertFalse(doctor.ENV_FILE.exists())

    def test_an_anthropic_key_is_refused_under_another_family(self):
        code, _, _ = self.run_keys("add", "openai", "--stdin",
                                   stdin="sk-ant-api03-0123456789abcdef")
        self.assertEqual(code, 1)
        self.assertFalse(doctor.ENV_FILE.exists())

    def test_malformed_keys_are_refused(self):
        for bad in ("", "short", "OPENAI_API_KEY=" + KEY, "two words 0123456789abcdef"):
            with self.subTest(bad=bad):
                code, _, err = self.run_keys("add", "openai", "--stdin", stdin=bad)
                self.assertEqual(code, 1)
                self.assertIn("Nothing was stored", err)
        self.assertFalse(doctor.ENV_FILE.exists())

    def test_unknown_family_is_a_usage_error(self):
        code, _, _ = self.run_keys("add", "acme", "--stdin", stdin=KEY)
        self.assertEqual(code, 2)

    def test_one_key_plus_paste_rest_makes_the_panel_ready(self):
        self.run_keys("add", "openai", "--stdin", stdin=KEY)
        code, out, _ = self.run_keys("paste-rest")
        self.assertEqual(code, 0)
        added = json.loads(out)["paste_seats_added"]
        self.assertEqual(len(added), 2)
        self.assertNotIn("openai", added)
        code, out, _ = self.run_keys("status")
        report = json.loads(out)
        self.assertEqual(code, 0)
        self.assertTrue(report["ready"])
        self.assertEqual(report["key_seats"], ["openai"])
        self.assertEqual(sorted(report["paste_seats"]), sorted(added))

    def test_paste_rest_on_a_full_panel_adds_nothing(self):
        os.environ.update({"OPENAI_API_KEY": KEY, "GEMINI_API_KEY": KEY,
                           "MOONSHOT_API_KEY": KEY})
        _, out, _ = self.run_keys("paste-rest")
        self.assertEqual(json.loads(out)["paste_seats_added"], [])
        self.assertFalse(doctor.ENV_FILE.exists())

    def test_storing_a_key_refreshes_the_cached_gate_check(self):
        doctor.CACHE.parent.mkdir(parents=True)
        doctor.CACHE.write_text(json.dumps({"checked_at": 9e18, "checks": [
            {"name": "Judge panel", "ok": False, "required": False, "detail": "0/3",
             "fix": "x"}]}))
        self.run_keys("add", "openai", "--stdin", stdin=KEY)
        self.run_keys("paste-rest")
        cached = json.loads(doctor.CACHE.read_text())["checks"]
        panel = next(c for c in cached if c["name"] == "Judge panel")
        self.assertTrue(panel["ok"])

    def test_remove_deletes_only_that_key(self):
        self.run_keys("add", "openai", "--stdin", stdin=KEY)
        self.run_keys("paste-rest")
        self.run_keys("remove", "openai")
        text = doctor.ENV_FILE.read_text()
        self.assertNotIn("OPENAI_API_KEY", text)
        self.assertIn(doctor.PASTE_SEATS_KEY, text)


class SkillsAskForAKeyTest(unittest.TestCase):
    """Every skill that leads into judging must send a short panel to the key prompt."""

    def test_judging_skills_point_at_the_key_prompt(self):
        for skill in ("pipeline", "design", "handover", "remediate"):
            with self.subTest(skill=skill):
                text = (ROOT / "skills" / skill / "SKILL.md").read_text()
                self.assertIn("references/judge-keys.md", text)

    def test_the_prompt_never_asks_for_the_key_in_chat(self):
        text = (ROOT / "skills" / "pipeline" / "references" / "judge-keys.md").read_text()
        self.assertIn("AskUserQuestion", text)
        self.assertIn("Never ask for the key in the chat", text)
        self.assertIn("pk keys add", text)


if __name__ == "__main__":
    unittest.main()
