"""The runtime registry (registry/) stays valid and its index.json never goes stale.

Apps pull registry/index.json to find their skills, agents and plugins. A stale index would
hand an app an old version silently, so CI fails on it here.
"""
from __future__ import annotations

import importlib.util
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_index", ROOT / "registry" / "build_index.py")
build_index = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_index)


def quiet(fn, *args):
    with redirect_stdout(io.StringIO()):
        return fn(*args)


class RegistryTest(unittest.TestCase):
    def test_every_node_is_valid(self):
        nodes, errors = build_index.load()
        errors += build_index.cross_check(nodes)
        self.assertEqual(errors, [])
        self.assertTrue(nodes["skill"], "the registry has no skills")

    def test_index_is_up_to_date(self):
        self.assertEqual(quiet(build_index.main, ["--check"]), 0,
                         "registry/index.json is stale: run python3 registry/build_index.py")

    def test_agent_steps_are_ordered_edges(self):
        index = json.loads((ROOT / "registry" / "index.json").read_text(encoding="utf-8"))
        calls = [e for e in index["edges"] if e["type"] == "calls" and e["from"] == "agent:weekly-coach"]
        self.assertEqual([e["order"] for e in calls], list(range(1, len(calls) + 1)))

    def test_skill_without_api_key_is_refused(self):
        folder = ROOT / "registry" / "skills" / "result-analyzer"
        node = json.loads((folder / "node.json").read_text(encoding="utf-8"))
        node["requires"] = []
        errors = build_index.check_node("skill", folder, node)
        self.assertTrue(any("apiKey" in e for e in errors))

    def test_unknown_provider_is_refused(self):
        folder = ROOT / "registry" / "skills" / "result-analyzer"
        node = json.loads((folder / "node.json").read_text(encoding="utf-8"))
        node["providers"] = {"llama": {"model": "x"}}
        errors = build_index.check_node("skill", folder, node)
        self.assertTrue(any("providers" in e for e in errors))

    def test_agent_step_must_exist(self):
        nodes, _ = build_index.load()
        nodes["agent"]["weekly-coach"] = dict(nodes["agent"]["weekly-coach"], steps=["no-such-skill"])
        errors = build_index.cross_check(nodes)
        self.assertTrue(any("no-such-skill" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
