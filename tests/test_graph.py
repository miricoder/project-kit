"""Tests for skills/graph/scripts/graph.py: the skills/pipeline graph and its exports."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "graph" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "pipeline" / "scripts"))

import graph  # noqa: E402
import state  # noqa: E402

FEATURE = """Feature: x
  Scenario: a task is filed
    Then a task exists
  Scenario: undo works
    Then it is undone
"""
BACKLOG = """# Backlog: demo

## Slice 1: Filing
- **Delivers:** filing
- **Scenarios:** a task is filed

## Slice 2: Undo
- **Scenarios:** undo works
"""


class GraphTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.saved = {k: os.environ.get(k) for k in ("PROJECT_KIT_GRAPH", "PROJECT_KIT_REGISTRY")}
        os.environ["PROJECT_KIT_GRAPH"] = str(base / "graph.db")
        os.environ["PROJECT_KIT_REGISTRY"] = str(base / "registry.json")
        self.addCleanup(self.restore)
        self.project = base / "demo"
        (self.project / "docs").mkdir(parents=True)
        (self.project / "docs" / "acceptance.feature").write_text(FEATURE)
        (self.project / "docs" / "backlog.md").write_text(BACKLOG)
        (self.project / "docs" / "spec.md").write_text("# spec")
        st = state.new_state("demo", mode="yolo")
        for phase in state.PHASES[:6]:
            st["phases"][phase]["status"] = "complete"
        st["phases"]["design"]["artifacts"] = ["docs/spec.md"]
        st["slices"] = {"1": {"status": "complete"}}
        state.save(st, self.project)
        self.conn = graph.connect()
        self.addCleanup(self.conn.close)

    def restore(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def synced(self):
        graph.sync(self.conn, [self.project])
        return graph.read(self.conn)

    def node(self, data, node_id):
        return next(n for n in data["nodes"] if n["id"] == node_id)

    # ---- collection ------------------------------------------------------------------

    def test_every_shipped_skill_is_a_node(self):
        data = self.synced()
        shipped = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
        skills = {n["props"]["name"].lstrip("/") for n in data["nodes"]
                  if n["label"] == "Skill" and n["props"]["exists"]}
        self.assertEqual(skills, shipped)
        self.assertIn("build", skills, "/build ships now; it must not show as missing")

    def test_phases_without_a_skill_are_missing_nodes(self):
        data = self.synced()
        missing = {n["caption"] for n in data["nodes"] if n["props"].get("missing")}
        shipped = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
        self.assertEqual(missing, {f"/{p}" for p in state.PHASES if p not in shipped})

    def test_project_pipeline_is_mapped(self):
        data = self.synced()
        rels = {(e["s"], e["type"], e["t"]) for e in data["edges"]}
        self.assertIn(("phase:demo:design", "NEXT", "phase:demo:handover"), rels)
        self.assertIn(("skill:build", "RUNS", "phase:demo:build"), rels)
        self.assertIn(("gate:demo:judge", "GUARDS", "phase:demo:initiate"), rels)
        self.assertIn(("phase:demo:design", "WRITES", "artifact:demo:docs/spec.md"), rels)
        self.assertIn(("project:demo", "AT_PHASE", "phase:demo:build"), rels)
        self.assertIn(("phase:demo:build", "BUILDS", "slice:demo:2"), rels)
        self.assertEqual(self.node(data, "slice:demo:1")["props"]["status"], "complete")
        self.assertEqual(self.node(data, "project:demo")["props"]["mode"], "yolo")

    def test_a_resync_reflects_the_new_state(self):
        self.synced()
        st = state.load(self.project)
        st["phases"]["build"]["status"] = "in progress"
        state.save(st, self.project)
        data = self.synced()
        self.assertEqual(self.node(data, "phase:demo:build")["props"]["status"], "in progress")

    def test_a_project_dropped_from_the_sync_disappears(self):
        self.synced()
        graph.sync(self.conn, [])
        ids = {n["id"] for n in graph.read(self.conn)["nodes"]}
        self.assertFalse([i for i in ids if ":demo" in i])
        self.assertIn("skill:build", ids)

    def test_unreadable_projects_are_reported_not_fatal(self):
        result = graph.sync(self.conn, [Path(self.tmp.name) / "nowhere"])
        self.assertEqual(len(result["errors"]), 1)

    # ---- exports ---------------------------------------------------------------------

    def test_cypher_merges_on_a_unique_id(self):
        cypher = graph.to_cypher(graph.layout(self.synced()))
        self.assertIn("REQUIRE n.pk_id IS UNIQUE", cypher)
        self.assertIn("MERGE (n:PkNode {pk_id: 'skill:build'})", cypher)
        self.assertIn("MERGE (a)-[r:RUNS]->(b)", cypher)
        self.assertNotIn("CREATE (", cypher, "re-running must update, never duplicate")
        for line in cypher.splitlines()[1:]:
            self.assertTrue(line.endswith(";"), line)

    def test_cypher_escapes_quotes(self):
        self.assertEqual(graph._cypher_value("it's"), "'it\\'s'")
        self.assertEqual(graph._cypher_value(True), "true")

    def test_standalone_html_carries_the_graph(self):
        page = graph.viewer_html(graph.layout(self.synced()))
        self.assertIn('"skill:build"', page)
        self.assertNotIn("/*GRAPH_DATA*/null", page)

    def test_embedded_data_cannot_close_the_script(self):
        data = {"nodes": [{"id": "x", "caption": "</script><b>"}], "edges": []}
        page = graph.viewer_html(data)
        self.assertNotIn("</script><b>", page)

    def test_layout_gives_every_node_a_seed(self):
        data = graph.layout(self.synced())
        for n in data["nodes"]:
            self.assertIn("sx", n)
            self.assertIn("sy", n)
        gaps = [e for e in data["edges"] if e["gap"]]
        self.assertTrue(gaps, "missing skills are drawn as gaps")

    # ---- serve -----------------------------------------------------------------------

    def test_server_serves_the_page_and_a_live_graph(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), graph.make_handler([self.project], False))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_address[1]}"
        page = urllib.request.urlopen(base + "/").read().decode()
        self.assertIn("const EMBEDDED = null", page)
        data = json.loads(urllib.request.urlopen(base + "/api/graph").read())
        self.assertIn("project:demo", {n["id"] for n in data["nodes"]})

    def test_cli_show_lists_missing_skills(self):
        graph.sync(self.conn, [self.project])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(graph.main(["show"]), 0)
        self.assertIn("/launch", json.loads(out.getvalue())["missing_skills"])


if __name__ == "__main__":
    unittest.main()
