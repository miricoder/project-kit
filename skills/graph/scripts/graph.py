#!/usr/bin/env python3
"""The Project Kit graph: skills, phases, gates, artifacts and build slices as nodes and
relationships, kept in a local SQLite database and viewable in any browser.

    graph.py sync [-C DIR] [--all]     rebuild the graph from the plugin's skills and the
                                       project in DIR (or every registered project)
    graph.py show                      counts per label and relationship type
    graph.py serve [--port 7474]       the interactive viewer at http://127.0.0.1:7474,
                   [--host 0.0.0.0]    re-synced on every page load (0.0.0.0: reachable
                                       from a phone on the same network)
    graph.py html -o FILE              a standalone viewer page with the graph inside it
    graph.py export --format cypher    Cypher for Neo4j (cypher-shell -f graph.cypher),
                   [--format json]     or the raw nodes and relationships as JSON
                   [-o FILE]

The database is ~/.claude/project-kit/graph.db (PROJECT_KIT_GRAPH overrides it). It is a
cache: every sync rebuilds it from SKILL.md files, pipeline.json and docs/backlog.md, so it
is never the source of truth and can be deleted at any time.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

HERE = Path(__file__).resolve()
PLUGIN_ROOT = HERE.parents[3]
VIEWER = HERE.parent.parent / "viewer.html"
sys.path.insert(0, str(PLUGIN_ROOT / "skills" / "pipeline" / "scripts"))
sys.path.insert(0, str(PLUGIN_ROOT / "skills" / "build" / "scripts"))

import state  # noqa: E402

try:
    import slices as slice_mod  # noqa: E402
except ImportError:  # pragma: no cover - shipped alongside
    slice_mod = None  # type: ignore[assignment]

LABELS = ("Project", "Phase", "Skill", "Gate", "Artifact", "Slice")
GAP_X, GAP_Y = 150, 760          # layout seeds: phase spacing, one band per project
# Relationships between skills that are not visible in any file Project Kit can parse.
SKILL_LINKS = (("remediate", "LOOPS", "handover"), ("remediate", "LOOPS", "verdict"),
               ("remediate", "HANDS_TO", "initiate"), ("initiate", "HANDS_TO", "build"))
SCHEMA = """
CREATE TABLE IF NOT EXISTS node (
  id TEXT PRIMARY KEY, label TEXT NOT NULL, caption TEXT NOT NULL,
  props TEXT NOT NULL, source TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS edge (
  src TEXT NOT NULL, type TEXT NOT NULL, dst TEXT NOT NULL, props TEXT NOT NULL,
  source TEXT NOT NULL, PRIMARY KEY (src, type, dst));
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def db_path() -> Path:
    return Path(os.path.expanduser(
        os.environ.get("PROJECT_KIT_GRAPH", "~/.claude/project-kit/graph.db")))


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    path = path or db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- collecting

class Graph:
    """Nodes and relationships collected from one source before they are written."""

    def __init__(self, source: str):
        self.source = source
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    def node(self, node_id: str, label: str, caption: str, **props: Any) -> str:
        clean = {k: v for k, v in props.items() if v is not None}
        self.nodes[node_id] = {"id": node_id, "label": label, "caption": caption,
                               "props": clean}
        return node_id

    def edge(self, src: str, rel: str, dst: str, **props: Any) -> None:
        self.edges[(src, rel, dst)] = {k: v for k, v in props.items() if v is not None}


def frontmatter(text: str) -> Dict[str, str]:
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    fields: Dict[str, str] = {}
    key = None
    for line in (match.group(1) if match else "").splitlines():
        if not line.startswith((" ", "\t")) and ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
        elif key and line.strip():
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def plugin_version(root: Path = PLUGIN_ROOT) -> str:
    try:
        return json.loads((root / ".claude-plugin" / "plugin.json").read_text())["version"]
    except (OSError, ValueError, KeyError):
        return "unknown"


def collect_skills(root: Path = PLUGIN_ROOT) -> Graph:
    """Every skill the plugin ships, plus a missing-skill node for each phase without one."""
    g = Graph("plugin")
    version = plugin_version(root)
    found = {}
    for path in sorted((root / "skills").glob("*/SKILL.md")):
        meta = frontmatter(path.read_text(encoding="utf-8"))
        name = meta.get("name") or path.parent.name
        scripts = sorted(p.name for p in (path.parent / "scripts").glob("*.py")) \
            if (path.parent / "scripts").is_dir() else []
        description = meta.get("description", "")
        found[name] = g.node(
            f"skill:{name}", "Skill", f"/{name}", name=f"/{name}", exists=True,
            status="available", phase=name if name in state.PHASES else None,
            description=description[:400] + ("…" if len(description) > 400 else ""),
            file=f"skills/{name}/SKILL.md", scripts=", ".join(scripts) or None,
            plugin_version=version)
    for phase in state.PHASES:
        if phase not in found:
            g.node(f"skill:{phase}", "Skill", f"/{phase}", name=f"/{phase}", exists=False,
                   status="missing", phase=phase, missing=True,
                   note="declared pipeline phase with no skill yet")
    for src, rel, dst in SKILL_LINKS:
        if f"skill:{src}" in g.nodes and f"skill:{dst}" in g.nodes:
            g.edge(f"skill:{src}", rel, f"skill:{dst}")
    return g


def collect_project(directory: Path) -> Graph:
    """One project's pipeline: phases, gates, artifacts, slices, and which skill runs what."""
    st = state.load(directory)
    name = st["project"]
    g = Graph(f"project:{name}")
    pid = f"project:{name}"
    nxt = state.next_phase(st)
    g.node(pid, "Project", name, name=name, path=str(directory.resolve()), mode=st["mode"],
           budget=f"${st['budget']['spent_usd']:.2f} of ${st['budget']['max_usd']:.2f}",
           next_phase=nxt or "complete", resume_point=st.get("resume_point"),
           status="complete" if nxt is None else "in progress", updated_at=st.get("updated_at"))
    g.edge("skill:pipeline", "CONDUCTS", pid)

    for i, phase in enumerate(state.PHASES):
        entry = st["phases"][phase]
        ph = g.node(f"phase:{name}:{phase}", "Phase", phase, name=phase, project=name,
                    order=i + 1, status=entry["status"], completed_at=entry.get("completed_at"),
                    blocked_reason=entry.get("blocked_reason"), skipped=entry.get("skipped"))
        if i:
            g.edge(f"phase:{name}:{state.PHASES[i - 1]}", "NEXT", ph)
        g.edge(f"skill:{phase}", "RUNS", ph)
        for artifact in entry.get("artifacts", []):
            exists = (directory / artifact).exists()
            aid = g.node(f"artifact:{name}:{artifact}", "Artifact", Path(artifact).name,
                         path=artifact, project=name, exists=exists,
                         status="complete" if exists else "missing")
            g.edge(ph, "WRITES", aid)
    if nxt:
        g.edge(pid, "AT_PHASE", f"phase:{name}:{nxt}")
        g.edge("skill:pipeline", "ROUTES_TO", f"skill:{nxt}", project=name)

    guarded = {gate: phase for phase, gate in state.GATED_BY.items()}
    for gate, record in st["gates"].items():
        status = "complete" if state.gate_passed(st, gate) else (
            "waived" if record.get("ruling") == "WAIVED" else record.get("status", "not started"))
        gid = g.node(f"gate:{name}:{gate}", "Gate", gate, name=gate, project=name,
                     ruling=record.get("ruling"), round=record.get("round"), status=status,
                     open_fixes=len(record.get("open_fixes") or []) or None,
                     reason=record.get("waived_reason"), decided_at=record.get("decided_at"))
        if gate in guarded:
            g.edge(gid, "GUARDS", f"phase:{name}:{guarded[gate]}")
        elif gate == "test":
            g.edge(gid, "CHECKS", f"phase:{name}:test")

    backlog = directory / "docs" / "backlog.md"
    if slice_mod is not None and backlog.is_file():
        try:
            parsed = slice_mod.parse_backlog(directory)
        except slice_mod.SliceError:
            parsed = []
        for item in parsed:
            record = (st.get("slices") or {}).get(str(item["number"]), {})
            sid = g.node(f"slice:{name}:{item['number']}", "Slice", f"Slice {item['number']}",
                         number=item["number"], name=item["name"], project=name,
                         status=record.get("status", "not started"),
                         scenarios=len(item["scenarios"]), delivers=item["delivers"] or None,
                         completed_at=record.get("completed_at"),
                         blocked_reason=record.get("blocked_reason"))
            g.edge(f"phase:{name}:build", "BUILDS", sid)
    return g


# --------------------------------------------------------------------------- storing

def write(conn: sqlite3.Connection, graph: Graph) -> None:
    with conn:
        conn.execute("DELETE FROM node WHERE source = ?", (graph.source,))
        conn.execute("DELETE FROM edge WHERE source = ?", (graph.source,))
        conn.executemany("INSERT OR REPLACE INTO node VALUES (?, ?, ?, ?, ?)", [
            (n["id"], n["label"], n["caption"], json.dumps(n["props"], sort_keys=True),
             graph.source) for n in graph.nodes.values()])
        conn.executemany("INSERT OR REPLACE INTO edge VALUES (?, ?, ?, ?, ?)", [
            (s, r, d, json.dumps(p, sort_keys=True), graph.source)
            for (s, r, d), p in graph.edges.items()])
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('synced_at', ?)", (_now(),))


def registered_projects() -> List[Path]:
    return [Path(row["path"]) for row in state.registry_load().get("projects", [])
            if row.get("path") and (Path(row["path"]) / state.STATE_FILE).is_file()]


def sync(conn: sqlite3.Connection, directories: Iterable[Path],
         root: Path = PLUGIN_ROOT) -> Dict[str, Any]:
    """Rebuild the graph: plugin skills, then each project. Projects no longer listed are
    dropped, so the graph never shows a pipeline that is not there any more."""
    write(conn, collect_skills(root))
    synced, errors = [], []
    for directory in directories:
        try:
            graph = collect_project(Path(directory))
        except (state.StateError, OSError, ValueError, KeyError) as exc:
            errors.append(f"{directory}: {exc}")
            continue
        write(conn, graph)
        synced.append(graph.source)
    with conn:
        stale = [row[0] for row in conn.execute(
            "SELECT DISTINCT source FROM node WHERE source LIKE 'project:%'")
            if row[0] not in synced]
        for source in stale:
            conn.execute("DELETE FROM node WHERE source = ?", (source,))
            conn.execute("DELETE FROM edge WHERE source = ?", (source,))
    return {"projects": [s.split(":", 1)[1] for s in synced], "errors": errors,
            "database": str(db_path())}


def read(conn: sqlite3.Connection) -> Dict[str, Any]:
    nodes = [{"id": i, "label": l, "caption": c, "props": json.loads(p)}
             for i, l, c, p in conn.execute(
                 "SELECT id, label, caption, props FROM node ORDER BY id")]
    ids = {n["id"] for n in nodes}
    edges = [{"s": s, "type": t, "t": d, "props": json.loads(p)}
             for s, t, d, p in conn.execute(
                 "SELECT src, type, dst, props FROM edge ORDER BY src, type, dst")
             if s in ids and d in ids]
    synced = conn.execute("SELECT value FROM meta WHERE key = 'synced_at'").fetchone()
    return {"nodes": nodes, "edges": edges, "synced_at": synced[0] if synced else None}


# --------------------------------------------------------------------------- views

def layout(graph: Dict[str, Any]) -> Dict[str, Any]:
    """Seed positions so each pipeline reads left to right, one band per project; the
    viewer's force layout starts from these."""
    projects = sorted({n["props"]["project"] for n in graph["nodes"]
                       if n["props"].get("project")} |
                      {n["caption"] for n in graph["nodes"] if n["label"] == "Project"})
    band = {name: i * GAP_Y for i, name in enumerate(projects)}
    order = {p: i for i, p in enumerate(state.PHASES)}
    writers = {e["t"]: e["s"] for e in graph["edges"] if e["type"] == "WRITES"}
    by_id = {n["id"]: n for n in graph["nodes"]}
    seen_per_phase: Dict[str, int] = {}
    extra_skill = 0
    for n in graph["nodes"]:
        p, label = n["props"], n["label"]
        y0 = band.get(p.get("project") or (n["caption"] if label == "Project" else ""), 0)
        if label == "Phase":
            n["sx"], n["sy"] = order[p["name"]] * GAP_X, y0
        elif label == "Project":
            n["sx"], n["sy"] = 6 * GAP_X, y0 - 330
        elif label == "Skill":
            phase = p.get("phase")
            if phase in order:
                n["sx"], n["sy"] = order[phase] * GAP_X, -150
            elif n["id"] == "skill:pipeline":
                n["sx"], n["sy"] = 3 * GAP_X, -330
            else:
                n["sx"], n["sy"] = (3.5 + extra_skill) * GAP_X, -260 - 40 * (extra_skill % 2)
                extra_skill += 1
        elif label == "Gate":
            target = {"judge": "initiate", "test": "test", "security": "launch"}.get(p["name"])
            n["sx"], n["sy"] = order.get(target, 5) * GAP_X - 40, y0 + 150
        elif label == "Artifact":
            writer = by_id.get(writers.get(n["id"], ""), {})
            col = order.get(writer.get("props", {}).get("name"), 5)
            k = seen_per_phase.get(writer.get("id", ""), 0)
            seen_per_phase[writer.get("id", "")] = k + 1
            n["sx"], n["sy"] = col * GAP_X + k * 60, y0 + 190 + k * 40
        elif label == "Slice":
            i = int(p.get("number", 1)) - 1
            n["sx"], n["sy"] = (3 + i % 7) * GAP_X, y0 + 430 + (i // 7) * 130
        else:
            n["sx"], n["sy"] = 0, y0
        n["status"] = p.get("status")
        n["missing"] = bool(p.get("missing"))
    missing = {n["id"] for n in graph["nodes"] if n["missing"]}
    for e in graph["edges"]:     # an arrow into or out of a missing skill is a gap
        e["gap"] = e["s"] in missing or e["t"] in missing
    return graph


def viewer_html(data: Optional[Dict[str, Any]] = None) -> str:
    page = VIEWER.read_text(encoding="utf-8")
    payload = json.dumps(data).replace("</", "<\\/") if data is not None else "null"
    return page.replace("/*GRAPH_DATA*/null", payload)


def _cypher_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    text = str(value).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    return f"'{text}'"


def _cypher_map(props: Dict[str, Any]) -> str:
    return "{" + ", ".join(f"`{k}`: {_cypher_value(v)}" for k, v in sorted(props.items())
                           if v is not None) + "}"


def to_cypher(graph: Dict[str, Any]) -> str:
    """Idempotent Cypher: MERGE on a unique pk_id, so re-running updates in place."""
    lines = ["// Project Kit graph. Load with: cypher-shell -f graph.cypher",
             "CREATE CONSTRAINT pk_node_id IF NOT EXISTS FOR (n:PkNode) REQUIRE n.pk_id IS UNIQUE;"]
    for n in graph["nodes"]:
        labels = ":".join(["PkNode", n["label"]] + (["Missing"] if n["props"].get("missing")
                                                     else []))
        props = {**n["props"], "caption": n["caption"]}
        lines.append(f"MERGE (n:PkNode {{pk_id: {_cypher_value(n['id'])}}}) "
                     f"SET n:{labels}, n += {_cypher_map(props)};")
    for e in graph["edges"]:
        lines.append(f"MATCH (a:PkNode {{pk_id: {_cypher_value(e['s'])}}}), "
                     f"(b:PkNode {{pk_id: {_cypher_value(e['t'])}}}) "
                     f"MERGE (a)-[r:{e['type']}]->(b)"
                     + (f" SET r += {_cypher_map(e['props'])}" if e["props"] else "") + ";")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- serve

def make_handler(directories: List[Path], use_registry: bool):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: str, kind: str) -> None:
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 - http.server API
            route = self.path.split("?", 1)[0]
            if route in ("/", "/index.html"):
                self._send(200, viewer_html(None), "text/html; charset=utf-8")
            elif route == "/api/graph":
                with lock:
                    conn = connect()
                    try:
                        dirs = registered_projects() if use_registry else directories
                        sync(conn, dirs)
                        body = json.dumps(layout(read(conn)))
                    finally:
                        conn.close()
                self._send(200, body, "application/json")
            else:
                self._send(404, "not found", "text/plain")

        def log_message(self, *args: Any) -> None:  # quiet
            return

    return Handler


# --------------------------------------------------------------------------- CLI

def _project_dirs(args: argparse.Namespace) -> List[Path]:
    if getattr(args, "all", False):
        return registered_projects()
    here = Path(args.dir)
    return [here] if (here / state.STATE_FILE).is_file() else []


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="graph.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-C", "--dir", default=".", help="project directory (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("sync", "serve", "html", "export"):
        p = sub.add_parser(name)
        p.add_argument("--all", action="store_true",
                       help="every project in the registry, not just -C")
        if name == "serve":
            p.add_argument("--port", type=int, default=7474)
            p.add_argument("--host", default="127.0.0.1")
        if name in ("html", "export"):
            p.add_argument("-o", "--output")
        if name == "export":
            p.add_argument("--format", choices=("cypher", "json"), default="cypher")
    sub.add_parser("show")
    args = parser.parse_args(argv)

    conn = connect()
    try:
        if args.command == "show":
            graph = read(conn)
            labels: Dict[str, int] = {}
            rels: Dict[str, int] = {}
            for n in graph["nodes"]:
                labels[n["label"]] = labels.get(n["label"], 0) + 1
            for e in graph["edges"]:
                rels[e["type"]] = rels.get(e["type"], 0) + 1
            missing = sorted(n["caption"] for n in graph["nodes"] if n["props"].get("missing"))
            print(json.dumps({"database": str(db_path()), "synced_at": graph["synced_at"],
                              "nodes": labels, "relationships": rels,
                              "missing_skills": missing}, indent=2))
            return 0

        result = sync(conn, _project_dirs(args))
        if args.command == "sync":
            print(json.dumps(result, indent=2))
            return 1 if result["errors"] else 0
        graph = layout(read(conn))
        if args.command == "html":
            out = Path(args.output or "project-kit-graph.html")
            out.write_text(viewer_html(graph), encoding="utf-8")
            print(json.dumps({"wrote": str(out), "nodes": len(graph["nodes"]),
                              "relationships": len(graph["edges"])}, indent=2))
            return 0
        if args.command == "export":
            text = to_cypher(graph) if args.format == "cypher" else \
                json.dumps({"nodes": graph["nodes"], "relationships": graph["edges"]}, indent=2)
            if args.output:
                Path(args.output).write_text(text, encoding="utf-8")
                print(json.dumps({"wrote": args.output, "format": args.format}, indent=2))
            else:
                sys.stdout.write(text)
            return 0
        if args.command == "serve":
            conn.close()
            server = ThreadingHTTPServer((args.host, args.port),
                                         make_handler(_project_dirs(args), args.all))
            shown = "127.0.0.1" if args.host in ("0.0.0.0", "") else args.host
            print(f"Project Kit graph at http://{shown}:{server.server_address[1]}/ "
                  f"(Ctrl+C to stop)", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return 0
    finally:
        try:
            conn.close()
        except sqlite3.ProgrammingError:
            pass
    return 2


if __name__ == "__main__":
    sys.exit(main())
