"""Tests for the documentation generator.

The registry test is the important one: these pages are committed and published, and the
registry holds the user's own project names and absolute paths.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs"))

import build_docs  # noqa: E402


class RegistryPrivacyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.registry = Path(self.tmp.name) / "registry.json"
        self.registry.write_text(json.dumps({"projects": [
            {"project": "a-private-project", "path": "/Users/someone/secret/place",
             "phase": "design", "mode": "auto", "judge_ruling": None,
             "launched": False, "updated_at": "2026-01-01T00:00:00+00:00"}]}))
        self._saved = os.environ.get("PROJECT_KIT_REGISTRY")
        os.environ["PROJECT_KIT_REGISTRY"] = str(self.registry)
        self.addCleanup(self._restore)
        self.addCleanup(self.tmp.cleanup)

    def _restore(self):
        if self._saved is None:
            os.environ.pop("PROJECT_KIT_REGISTRY", None)
        else:
            os.environ["PROJECT_KIT_REGISTRY"] = self._saved

    def test_registry_is_not_read_by_default(self):
        self.assertEqual(build_docs.read_registry(), [])

    def test_registry_is_read_only_when_asked(self):
        rows = build_docs.read_registry(include=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["project"], "a-private-project")

    def test_generated_pages_never_leak_the_registry_by_default(self):
        """The committed, published pages must not contain project names or paths."""
        for path, text in build_docs.render().items():
            with self.subTest(page=path.name):
                self.assertNotIn("a-private-project", text)
                self.assertNotIn("/Users/someone/secret/place", text)

    def test_the_tracker_shows_an_empty_state_by_default(self):
        pages = build_docs.render()
        knowhow = next(t for p, t in pages.items() if "know_how" in p.name)
        self.assertIn("No projects yet", knowhow)

    def test_a_personal_copy_can_include_it(self):
        pages = build_docs.render(with_registry=True)
        knowhow = next(t for p, t in pages.items() if "know_how" in p.name)
        self.assertIn("a-private-project", knowhow)


class DeterminismTest(unittest.TestCase):
    """Generated output must not depend on the machine, or the staleness gate in CI
    fails for reasons unrelated to the change being made."""

    def test_two_renders_agree(self):
        first, second = build_docs.render(), build_docs.render()
        self.assertEqual({p.name: t for p, t in first.items()},
                         {p.name: t for p, t in second.items()})

    def test_every_page_cross_links_the_others(self):
        pages = {p.name: t for p, t in build_docs.render().items()}
        self.assertEqual(set(pages),
                         {"index.html", "walkthrough.html", "project_kit_know_how.html"})
        for name, text in pages.items():
            for other in pages:
                if other != name:
                    with self.subTest(page=name, links_to=other):
                        self.assertIn(other, text)


if __name__ == "__main__":
    unittest.main()
