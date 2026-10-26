#!/usr/bin/env python3
"""Quality checks for a Project Kit project: everything /remediate loops on until it passes.

    qa.py                  run every check below; exit 0 only when all pass
    qa.py lint             the plan: spec sections, failure modes -> scenarios, decisions,
                           rollback, acceptance scenarios with outcomes
    qa.py a11y [FILE...]   accessibility of the UI mockups (ui/**/*.html, *.dc.html):
                           axe-core WCAG 2.1 A/AA, keyboard focus, reflow at 320px
    qa.py backlog          every acceptance scenario is in a backlog slice
    qa.py hook             PostToolUse hook: re-scan a UI file Claude just wrote; exit 2
                           with the failures so Claude fixes them before moving on

Writes <project>/qa/report.json. Exit codes: 0 pass, 1 fail (problems listed), 2 usage
error — except `hook`, which follows the hook contract (2 = feed stderr back to Claude).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "pipeline" / "scripts"))

import state  # noqa: E402

SPEC = "docs/spec.md"
FEATURE = "docs/acceptance.feature"
BACKLOG = "docs/backlog.md"
REPORT = "qa/report.json"

# Mirrors skills/design/references/spec-template.md. A test keeps them in step.
SPEC_SECTIONS = ("Architecture", "Decisions", "Data model", "Interfaces", "Failure modes",
                 "Rollback", "Security and privacy", "Not built", "Strongest counter-argument")

AXE_VERSION = "4.10.2"
A11Y_HOME = Path(os.path.expanduser(
    os.environ.get("PROJECT_KIT_A11Y_HOME", "~/.claude/project-kit/a11y")))
SCANNER = ROOT / "scripts" / "a11y_scan.js"
UI_SKIP = {"node_modules", ".git", "judge", "qa"}


def problem(check: str, detail: str) -> Dict[str, str]:
    return {"check": check, "detail": detail}


# --------------------------------------------------------------------------- markdown

def section(markdown: str, heading: str) -> Optional[str]:
    """Body of `## heading`, or None when the heading is absent."""
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", markdown, re.M | re.S)
    return match.group(1).strip() if match else None


def table_rows(body: str) -> List[List[str]]:
    """Data rows of the first markdown table in `body` (header and rule skipped)."""
    rows = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    cells = [[c.strip() for c in row.strip("|").split("|")] for row in rows]
    data = [c for c in cells[1:] if not all(re.fullmatch(r":?-{2,}:?", x or "--") for x in c)]
    return [r for r in data if any(r)]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().strip("`'\"").lower())


def scenarios(feature: str) -> Dict[str, List[str]]:
    """Scenario name -> its step keywords."""
    out: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for line in feature.splitlines():
        head = re.match(r"\s*Scenario(?: Outline)?:\s*(.+?)\s*$", line)
        if head:
            current = head.group(1)
            out[current] = []
            continue
        step = re.match(r"\s*(Given|When|Then|And|But)\b", line)
        if step and current is not None:
            out[current].append(step.group(1))
    return out


# --------------------------------------------------------------------------- lint

def lint(project: Path) -> List[Dict[str, str]]:
    problems: List[Dict[str, str]] = []
    spec_path, feature_path = project / SPEC, project / FEATURE
    if not spec_path.is_file():
        return [problem("spec", f"{SPEC} is missing")]
    if not feature_path.is_file():
        return [problem("acceptance", f"{FEATURE} is missing")]
    spec, feature = spec_path.read_text(), feature_path.read_text()

    for heading in SPEC_SECTIONS:
        body = section(spec, heading)
        if body is None:
            problems.append(problem("spec", f"section '## {heading}' is missing"))
        elif not body or body.startswith("<") or (
                all(line.strip().startswith("|") for line in body.splitlines() if line.strip())
                and not table_rows(body)):
            problems.append(problem("spec", f"section '## {heading}' is empty or a placeholder"))

    found = scenarios(feature)
    if not re.search(r"^\s*Feature:", feature, re.M):
        problems.append(problem("acceptance", "no Feature: block"))
    if not found:
        problems.append(problem("acceptance", "no scenarios"))
    for name, steps in found.items():
        if "Then" not in steps:
            problems.append(problem("acceptance", f"scenario '{name}' has no Then (no outcome)"))
    names = {_norm(n) for n in found}

    for row in table_rows(section(spec, "Failure modes") or ""):
        failure = row[0] if row else "?"
        scenario = row[2] if len(row) > 2 else ""
        if not scenario:
            problems.append(problem("failure-modes", f"'{failure}' names no scenario"))
        elif _norm(scenario) not in names:
            problems.append(problem("failure-modes",
                                    f"'{failure}' points at scenario '{scenario}', which is not "
                                    f"in {FEATURE}"))
    for row in table_rows(section(spec, "Decisions") or ""):
        if len(row) < 3 or not row[2]:
            problems.append(problem("decisions", f"'{row[0]}' names no rejected alternative"))
    rollback = {(_norm(r[0]) if r else ""): r for r in table_rows(section(spec, "Rollback") or "")}
    for layer in ("code", "data"):
        row = rollback.get(layer)
        if not row or len(row) < 2 or not row[1]:
            problems.append(problem("rollback", f"no rollback stated for {layer}"))
    return problems


def backlog(project: Path) -> List[Dict[str, str]]:
    path, feature_path = project / BACKLOG, project / FEATURE
    if not path.is_file():
        return [problem("backlog", f"{BACKLOG} is missing")]
    text = path.read_text()
    problems = []
    if not re.search(r"^##\s+Slice\s+\d+", text, re.M):
        problems.append(problem("backlog", "no '## Slice <n>' headings"))
    lowered = _norm(text)
    feature = feature_path.read_text() if feature_path.is_file() else ""
    for name in scenarios(feature):
        if _norm(name) not in lowered:
            problems.append(problem("backlog", f"scenario '{name}' is in no slice"))
    return problems


# --------------------------------------------------------------------------- a11y

def ui_files(project: Path) -> List[Path]:
    found = []
    for path in sorted(project.rglob("*.html")):
        rel = path.relative_to(project)
        if UI_SKIP & set(rel.parts[:-1]):
            continue
        if path.name.endswith(".dc.html") or (rel.parts and rel.parts[0] == "ui"):
            found.append(path)
    return found


def flatten(raw: str, accent: str = "#1E6A86") -> str:
    """A design-canvas artboard (.dc.html) as plain HTML a browser can scan: the helmet's
    styles move to <head>, template holes take their defaults, scripts are dropped."""
    if "<x-dc>" not in raw:
        return raw
    title = (re.search(r"<title>(.*?)</title>", raw, re.S) or [None, "Artboard"])[1]
    helmet = (re.search(r"<helmet>(.*?)</helmet>", raw, re.S) or [None, ""])[1]
    style = (re.search(r"<style>.*?</style>", helmet, re.S) or [""])[0]
    body = raw.split("</helmet>", 1)[-1].split("</x-dc>", 1)[0]
    props = re.search(r"data-props='(.*?)'", raw, re.S)
    defaults: Dict[str, Any] = {}
    if props:
        try:
            defaults = {k: v.get("default") for k, v in json.loads(props.group(1)).items()
                        if isinstance(v, dict) and "default" in v}
        except json.JSONDecodeError:
            pass
    defaults.setdefault("accent", accent)
    body = re.sub(r'(\w+)="\{\{\s*true\s*\}\}"',
                  lambda m: "checked" if m.group(1) == "defaultChecked" else f'{m.group(1)}=""', body)
    body = re.sub(r"\{\{\s*([\w.$]+)\s*\}\}", lambda m: str(defaults.get(m.group(1), "")), body)
    lang = (re.search(r'<html lang="([\w-]+)"', raw) or [None, "en"])[1]
    return (f'<!doctype html><html lang="{lang}">'
            f'<head><meta charset="utf-8"><title>{title}</title>{style}</head>'
            f"<body>{body}</body></html>")


def scanner_ready() -> Optional[str]:
    """None when node, playwright and axe-core are usable; otherwise how to fix it."""
    if not shutil.which("node"):
        return "node is not installed: install Node.js 18+ to scan UI mockups"
    axe = A11Y_HOME / "node_modules" / "axe-core" / "axe.min.js"
    if not axe.is_file():
        if not shutil.which("npm"):
            return "npm is not installed: needed once to fetch axe-core"
        A11Y_HOME.mkdir(parents=True, exist_ok=True)
        done = subprocess.run(["npm", "install", "--prefix", str(A11Y_HOME), "--no-audit",
                               "--no-fund", f"axe-core@{AXE_VERSION}"],
                              capture_output=True, text=True, timeout=300)
        if done.returncode != 0 or not axe.is_file():
            return f"could not install axe-core: {(done.stderr or '').strip()[-200:]}"
    probe = subprocess.run(["node", "-e", "require('playwright')"], capture_output=True,
                           text=True, env=_node_env(), timeout=60)
    if probe.returncode != 0:
        return (f"playwright is not installed: npm install --prefix {A11Y_HOME} playwright "
                "&& npx --prefix " + str(A11Y_HOME) + " playwright install chromium")
    return None


def _node_env() -> Dict[str, str]:
    paths = [str(A11Y_HOME / "node_modules")] + \
        [p for p in os.environ.get("NODE_PATH", "").split(os.pathsep) if p]
    return {**os.environ, "NODE_PATH": os.pathsep.join(paths)}


def evaluate(results: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Problems from the scanner's per-file results. Pure, so it is tested without a browser."""
    problems = []
    for r in results:
        name = r["file"]
        for v in r.get("violations", []):
            where = "; ".join(v.get("targets", [])[:3])
            problems.append(problem("a11y", f"{name}: {v['id']} ({v.get('impact')}) "
                                             f"{v.get('help')} — {where}"))
        for stop in r.get("focusMissing", []):
            problems.append(problem("a11y", f"{name}: no visible focus on '{stop}' (2.4.7)"))
        if r.get("overflow320"):
            problems.append(problem("a11y", f"{name}: scrolls sideways at 320px (1.4.10)"))
        if r.get("error"):
            problems.append(problem("a11y", f"{name}: could not scan: {r['error']}"))
    return problems


def a11y(project: Path, files: Optional[Sequence[Path]] = None) -> List[Dict[str, str]]:
    targets = list(files) if files else ui_files(project)
    if not targets:
        return []
    why = scanner_ready()
    if why:
        return [problem("a11y", f"{len(targets)} UI file(s) not scanned: {why}")]
    with tempfile.TemporaryDirectory() as tmp:
        flat = []
        for i, path in enumerate(targets):
            out = Path(tmp) / f"{i}.html"
            out.write_text(flatten(path.read_text()))
            flat.append((str(path.relative_to(project) if path.is_relative_to(project) else path),
                         str(out)))
        report = Path(tmp) / "report.json"
        axe = A11Y_HOME / "node_modules" / "axe-core" / "axe.min.js"
        done = subprocess.run(["node", str(SCANNER), str(axe), str(report),
                               json.dumps(flat)], capture_output=True, text=True,
                              env=_node_env(), timeout=600)
        if done.returncode != 0 or not report.is_file():
            return [problem("a11y", f"scanner failed: {(done.stderr or done.stdout).strip()[-300:]}")]
        return evaluate(json.loads(report.read_text()))


# --------------------------------------------------------------------------- report

def judge_status(project: Path) -> List[Dict[str, str]]:
    try:
        st = state.load(project)
    except state.StateError:
        return [problem("judge", "no pipeline.json")]
    if state.gate_passed(st, "judge"):
        return []
    record = st["gates"]["judge"]
    detail = record.get("ruling") or "not judged yet"
    fixes = record.get("open_fixes") or []
    return [problem("judge", f"judge gate not passed ({detail}"
                             + (f", {len(fixes)} fix(es) open)" if fixes else ")"))]


def write_report(project: Path, checks: Dict[str, List[Dict[str, str]]]) -> Dict[str, Any]:
    report = {"passed": not any(checks.values()),
              "checks": {k: {"passed": not v, "problems": v} for k, v in checks.items()}}
    path = project / REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


def project_of(path: Path) -> Optional[Path]:
    for candidate in (path if path.is_dir() else path.parent, *path.parents):
        if (candidate / state.STATE_FILE).is_file():
            return candidate
    return None


def hook(stdin: str) -> int:
    """PostToolUse: after Claude writes a UI mockup inside a Project Kit project, scan it.
    Anything else, or any failure of the hook itself, is a silent pass: a hook must never
    block unrelated work."""
    try:
        data = json.loads(stdin or "{}")
        path = Path((data.get("tool_input") or {}).get("file_path", ""))
    except (json.JSONDecodeError, AttributeError):
        return 0
    if not path.name or path.suffix != ".html" or not path.is_file():
        return 0
    project = project_of(path.resolve())
    if project is None or path.resolve() not in {p.resolve() for p in ui_files(project)}:
        return 0
    try:
        problems = a11y(project, [path.resolve()])
    except (OSError, subprocess.SubprocessError):
        return 0
    if not problems:
        return 0
    print(f"Accessibility re-scan of {path.name} failed. Fix these, then they are re-checked "
          "automatically:", file=sys.stderr)
    for p in problems:
        print(f"  - {p['detail']}", file=sys.stderr)
    return 2


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="qa.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-C", "--dir", default=".", help="project directory (default: cwd)")
    parser.add_argument("check", nargs="?", default="all",
                        choices=("all", "lint", "a11y", "backlog", "hook"))
    parser.add_argument("files", nargs="*", help="a11y: only these files")
    args = parser.parse_args(argv)

    if args.check == "hook":
        return hook(sys.stdin.read())
    project = Path(args.dir).resolve()
    if args.check == "lint":
        checks = {"lint": lint(project)}
    elif args.check == "a11y":
        checks = {"a11y": a11y(project, [Path(f).resolve() for f in args.files] or None)}
    elif args.check == "backlog":
        checks = {"backlog": backlog(project)}
    else:
        checks = {"lint": lint(project), "a11y": a11y(project), "judge": judge_status(project)}
    report = write_report(project, checks)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
