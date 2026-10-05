"""Structural checks on the plugin manifests and every skill's frontmatter.

These run in CI without needing the Claude Code CLI, and catch the mistakes that actually
happen: a version drifting between the two manifests, a skill whose directory name does not
match its frontmatter, or a placeholder description left in place.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
MARKET = ROOT / ".claude-plugin" / "marketplace.json"
SKILLS = ROOT / "skills"
AGENTS = ROOT / "agents"

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_PLACEHOLDER = re.compile(r"\bTODO\b")


def frontmatter(path: Path) -> dict[str, str]:
    """Parse the subset of YAML the frontmatter uses: top-level `key: value` pairs, with
    values optionally continued on following indented lines."""
    match = _FRONTMATTER.match(path.read_text())
    if not match:
        raise AssertionError(f"{path}: no YAML frontmatter block")
    fields: dict[str, str] = {}
    key = None
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")) and ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
        elif key:
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


class ManifestTest(unittest.TestCase):
    def test_plugin_manifest_has_required_fields(self):
        data = json.loads(PLUGIN.read_text())
        for field in ("name", "version", "description", "author"):
            self.assertIn(field, data, f"plugin.json missing {field!r}")
        self.assertEqual(data["name"], "project-kit")
        self.assertRegex(data["version"], r"^\d+\.\d+\.\d+$")
        self.assertNotRegex(data["description"], _PLACEHOLDER)

    def test_marketplace_version_agrees_with_plugin(self):
        plugin = json.loads(PLUGIN.read_text())
        market = json.loads(MARKET.read_text())
        entries = [p for p in market["plugins"] if p["name"] == plugin["name"]]
        self.assertEqual(len(entries), 1, "exactly one marketplace entry for this plugin")
        self.assertEqual(
            entries[0]["version"], plugin["version"],
            "marketplace.json and plugin.json versions must agree, or `claude plugin tag` refuses")

    def test_declared_skill_paths_exist(self):
        for rel in json.loads(PLUGIN.read_text()).get("skills", []):
            self.assertTrue((ROOT / rel).is_dir(), f"declared skills path missing: {rel}")


class SkillFrontmatterTest(unittest.TestCase):
    def skill_files(self) -> list[Path]:
        found = sorted(SKILLS.glob("*/SKILL.md"))
        self.assertTrue(found, "no skills found under skills/")
        return found

    def test_every_skill_has_name_and_description(self):
        for path in self.skill_files():
            with self.subTest(skill=path.parent.name):
                fields = frontmatter(path)
                self.assertIn("name", fields)
                self.assertIn("description", fields)
                self.assertTrue(fields["description"].strip())

    def test_skill_directory_matches_frontmatter_name(self):
        for path in self.skill_files():
            with self.subTest(skill=path.parent.name):
                self.assertEqual(
                    frontmatter(path)["name"], path.parent.name,
                    "the directory name is how the skill is invoked; it must match `name`")

    def test_no_placeholder_descriptions_ship(self):
        for path in self.skill_files():
            with self.subTest(skill=path.parent.name):
                self.assertNotRegex(frontmatter(path)["description"], _PLACEHOLDER)

    def test_agents_have_name_and_description(self):
        for path in sorted(AGENTS.glob("*.md")):
            with self.subTest(agent=path.stem):
                fields = frontmatter(path)
                self.assertEqual(fields.get("name"), path.stem)
                self.assertNotRegex(fields.get("description", "TODO"), _PLACEHOLDER)


if __name__ == "__main__":
    unittest.main()
