#!/usr/bin/env python3
"""Build slices for Project Kit: the mechanical half of /build.

    slices.py list                     every slice in docs/backlog.md with its status
    slices.py next                     the slice to build next, and whether it may start
    slices.py start <n>                mark slice n in progress (build phase in progress)
    slices.py check <n>                may slice n be marked done? (tests pass, scenarios mapped)
    slices.py done <n>                 run `check`, then record slice n complete
    slices.py block <n> --reason ...   record why slice n cannot proceed
    slices.py config --test-command "python -m pytest -q" [--tests tests]

A slice is done only when its own scenarios are named in the project's tests and the test
command exits 0. Both are checked here, by a script, never asserted by a model. When the
last slice is done the build phase is recorded complete.

Slice state lives in pipeline.json under "slices" and "build"; both keys are optional, so
older state files load unchanged. Exit codes: 0 ok, 1 refused (reasons on stderr), 2 usage
or state error.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "pipeline" / "scripts"))
sys.path.insert(0, str(HERE.parents[3] / "scripts"))

import state  # noqa: E402
from qa import BACKLOG, FEATURE, _norm, scenarios  # noqa: E402

DEFAULT_TESTS = ("tests", "test", "__tests__", "spec", "e2e")
TEST_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rb", ".java",
                 ".kt", ".swift", ".rs", ".feature", ".php", ".cs"}
SKIP_DIRS = {"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build"}
TEST_TIMEOUT = 1800
STATUSES = ("not started", "in progress", "blocked", "complete")


class SliceError(RuntimeError):
    """A slice precondition was not met."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- backlog

def parse_backlog(project: Path) -> List[Dict[str, Any]]:
    """Slices in build order: number, name, the scenarios named in the slice, its text."""
    path = project / BACKLOG
    if not path.is_file():
        raise SliceError(f"{BACKLOG} is missing; run /initiate first")
    text = path.read_text(encoding="utf-8")
    feature_path = project / FEATURE
    names = list(scenarios(feature_path.read_text(encoding="utf-8"))) \
        if feature_path.is_file() else []
    heads = list(re.finditer(r"^##\s+Slice\s+(\d+)\s*[:.\-–—]?\s*(.*?)\s*$", text, re.M))
    if not heads:
        raise SliceError(f"{BACKLOG} has no '## Slice <n>: <name>' headings")
    slices = []
    for i, head in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        nxt = re.search(r"^##\s", text[head.end():end], re.M)
        body = text[head.end(): head.end() + nxt.start()] if nxt else text[head.end():end]
        flat = _norm(body)
        field = lambda label: (re.search(rf"\*\*{label}:\*\*\s*(.+?)(?=\n-\s+\*\*|\Z)",  # noqa: E731
                                         body, re.S) or [None, ""])[1]
        slices.append({
            "number": int(head.group(1)),
            "name": head.group(2) or f"Slice {head.group(1)}",
            "delivers": " ".join(field("Delivers").split()),
            "done_when": " ".join(field("Done when").split()),
            "scenarios": [n for n in names if _norm(n) in flat],
        })
    return slices


# --------------------------------------------------------------------------- state

def slice_record(st: Dict[str, Any], number: int) -> Dict[str, Any]:
    return st.setdefault("slices", {}).setdefault(str(number), {"status": "not started"})


def status_of(st: Dict[str, Any], number: int) -> str:
    return (st.get("slices") or {}).get(str(number), {}).get("status", "not started")


def build_config(st: Dict[str, Any]) -> Dict[str, Any]:
    return st.setdefault("build", {})


def find(slices: List[Dict[str, Any]], number: int) -> Dict[str, Any]:
    for item in slices:
        if item["number"] == number:
            return item
    raise SliceError(f"no slice {number} in {BACKLOG}")


def next_slice(st: Dict[str, Any], slices: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for item in slices:
        if status_of(st, item["number"]) != "complete":
            return item
    return None


def start_blockers(st: Dict[str, Any], slices: List[Dict[str, Any]], number: int) -> List[str]:
    """Why slice `number` may not start. Earlier slices need not be finished (the backlog
    order is a recommendation), but the build phase itself must be allowed to run."""
    find(slices, number)
    reasons = list(state.blockers(st, "build"))
    if status_of(st, number) == "complete":
        reasons.append(f"slice {number} is already complete")
    return reasons


# --------------------------------------------------------------------------- checks

def test_files(project: Path, roots: List[str]) -> List[Path]:
    found: List[Path] = []
    for root in roots:
        base = project / root
        if base.is_file():
            found.append(base)
            continue
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in TEST_SUFFIXES \
                    and not SKIP_DIRS.intersection(path.relative_to(project).parts):
                found.append(path)
    return found


def unmapped_scenarios(project: Path, scenario_names: List[str], roots: List[str]) -> List[str]:
    """Scenarios whose exact name appears in no test file (case and spacing ignored)."""
    corpus = " ".join(_norm(p.read_text(encoding="utf-8", errors="replace"))
                      for p in test_files(project, roots))
    return [name for name in scenario_names if _norm(name) not in corpus]


def run_tests(project: Path, command: str) -> Dict[str, Any]:
    try:
        proc = subprocess.run(shlex.split(command), cwd=project, capture_output=True,
                              text=True, timeout=TEST_TIMEOUT)
    except FileNotFoundError as exc:
        return {"exit": 127, "tail": str(exc)}
    except subprocess.TimeoutExpired:
        return {"exit": 124, "tail": f"timed out after {TEST_TIMEOUT} s"}
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-15:])
    return {"exit": proc.returncode, "tail": tail}


def done_blockers(project: Path, st: Dict[str, Any], item: Dict[str, Any],
                  run: bool = True) -> List[str]:
    reasons: List[str] = []
    cfg = build_config(st)
    command = cfg.get("test_command")
    roots = cfg.get("tests") or list(DEFAULT_TESTS)
    if status_of(st, item["number"]) == "not started":
        reasons.append(f"slice {item['number']} was never started (slices.py start "
                       f"{item['number']})")
    if not item["scenarios"]:
        reasons.append(f"slice {item['number']} names no scenario from {FEATURE}; a slice is "
                       "done when its scenarios pass, so it cannot be checked")
    if not test_files(project, roots):
        reasons.append(f"no test files under {', '.join(roots)} "
                       "(set the folders with: slices.py config --tests <dir>)")
    for name in unmapped_scenarios(project, item["scenarios"], roots):
        reasons.append(f"scenario not named in any test: '{name}'")
    if not command:
        reasons.append("no test command recorded "
                       "(slices.py config --test-command \"python -m pytest -q\")")
    elif run and not reasons:
        result = run_tests(project, command)
        if result["exit"] != 0:
            reasons.append(f"test command failed (exit {result['exit']}): {command}\n"
                           + result["tail"])
    return reasons


# --------------------------------------------------------------------------- CLI

def _emit(data: Any) -> None:
    print(json.dumps(data, indent=2))


def _refuse(reasons: List[str]) -> int:
    print("REFUSED", file=sys.stderr)
    for reason in reasons:
        print(f"  - {reason}", file=sys.stderr)
    return 1


def _view(st: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    record = (st.get("slices") or {}).get(str(item["number"]), {})
    out = {"number": item["number"], "name": item["name"],
           "status": record.get("status", "not started"),
           "scenarios": item["scenarios"], "delivers": item["delivers"]}
    for key in ("started_at", "completed_at", "blocked_reason"):
        if key in record:
            out[key] = record[key]
    return out


def _finish_phase_if_done(st: Dict[str, Any], slices: List[Dict[str, Any]]) -> bool:
    if all(status_of(st, s["number"]) == "complete" for s in slices):
        state.set_phase(st, "build", "complete")
        return True
    return False


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="slices.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-C", "--dir", default=".", help="project directory (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="every slice with its status")
    sub.add_parser("next", help="the slice to build next")
    for name in ("start", "check", "done"):
        sub.add_parser(name).add_argument("number", type=int)
    p = sub.add_parser("block")
    p.add_argument("number", type=int)
    p.add_argument("--reason", required=True)
    p = sub.add_parser("config", help="record how this project runs its tests")
    p.add_argument("--test-command")
    p.add_argument("--tests", action="append", help="a test folder or file (repeatable)")
    args = parser.parse_args(argv)

    project = Path(args.dir)
    try:
        st = state.load(project)
        if args.command == "config":
            cfg = build_config(st)
            if args.test_command:
                cfg["test_command"] = args.test_command
            if args.tests:
                cfg["tests"] = args.tests
            if args.test_command or args.tests:
                state.save(st, project)
            _emit({"test_command": cfg.get("test_command"),
                   "tests": cfg.get("tests") or list(DEFAULT_TESTS)})
            return 0

        slices = parse_backlog(project)
        if args.command == "list":
            done = sum(status_of(st, s["number"]) == "complete" for s in slices)
            _emit({"slices": [_view(st, s) for s in slices], "complete": done,
                   "total": len(slices)})
            return 0
        if args.command == "next":
            item = next_slice(st, slices)
            if item is None:
                _emit({"slice": None, "note": "every slice is complete"})
                return 0
            reasons = start_blockers(st, slices, item["number"]) \
                if status_of(st, item["number"]) != "in progress" else \
                list(state.blockers(st, "build"))
            _emit({"slice": _view(st, item), "runnable": not reasons, "blockers": reasons,
                   "mode": st["mode"], "test_command": build_config(st).get("test_command")})
            return 0

        item = find(slices, args.number)
        if args.command == "start":
            if status_of(st, args.number) == "in progress":
                _emit({"slice": _view(st, item), "note": "already in progress"})
                return 0
            reasons = start_blockers(st, slices, args.number)
            if reasons:
                return _refuse(reasons)
            record = slice_record(st, args.number)
            record.update(status="in progress", name=item["name"], started_at=_now())
            record.pop("blocked_reason", None)
            if st["phases"]["build"]["status"] != "in progress":
                state.set_phase(st, "build", "in progress")
            state.save(st, project)
            state.registry_upsert(st, project)
            _emit({"slice": _view(st, item)})
            return 0
        if args.command == "check":
            reasons = done_blockers(project, st, item)
            if reasons:
                return _refuse(reasons)
            _emit({"slice": item["number"], "ready": True})
            return 0
        if args.command == "done":
            reasons = done_blockers(project, st, item)
            if reasons:
                return _refuse(reasons)
            record = slice_record(st, args.number)
            record.update(status="complete", name=item["name"], completed_at=_now())
            record.pop("blocked_reason", None)
            build_complete = _finish_phase_if_done(st, slices)
            st["resume_point"] = state.describe_next(st)
            state.save(st, project)
            state.registry_upsert(st, project)
            following = next_slice(st, slices)
            _emit({"slice": _view(st, item), "build_complete": build_complete,
                   "next_slice": _view(st, following) if following else None,
                   "next": state.describe_next(st)})
            return 0
        if args.command == "block":
            record = slice_record(st, args.number)
            record.update(status="blocked", name=item["name"], blocked_reason=args.reason)
            state.save(st, project)
            _emit({"slice": _view(st, item)})
            return 0
    except (state.StateError, SliceError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
