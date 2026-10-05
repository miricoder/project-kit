#!/usr/bin/env python3
"""Pipeline state for Project Kit.

Owns two files:

  <project>/pipeline.json              per-project phase, gates, mode, budget
  ~/.claude/project-kit/registry.json  one row per project, for the tracker page

Everything a gate depends on is recorded here by a script, never asserted by a model.
Pure functions do the work; the CLI at the bottom is a thin wrapper so skills can call it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SCHEMA_VERSION = 1
STATE_FILE = "pipeline.json"
def registry_path() -> Path:
    """User-level registry the tracker page reads. PROJECT_KIT_REGISTRY overrides it, which
    keeps tests and smoke runs out of the real file."""
    return Path(os.path.expanduser(
        os.environ.get("PROJECT_KIT_REGISTRY", "~/.claude/project-kit/registry.json")))

# Phase order is the pipeline order. Wave 1 is ideate..verdict; the rest are declared so
# state, gates and the tracker already understand them.
PHASES: tuple[str, ...] = (
    "ideate", "proposal", "design", "handover", "verdict",
    "initiate", "build", "devops", "test", "security", "launch",
)
WAVE1: tuple[str, ...] = PHASES[:5]

# House-style status enum (.github/continuity_protocol.md).
STATUSES = ("not started", "in progress", "blocked", "complete")
MODES = ("manual", "auto", "yolo")
GATES = ("judge", "test", "security")

# Phases that may not start until a gate has passed.
GATED_BY: Dict[str, str] = {"initiate": "judge", "launch": "security"}

# In `auto`, the pipeline pauses after these phases. `manual` pauses after every phase;
# `yolo` after none.
AUTO_CHECKPOINTS: tuple[str, ...] = ("ideate", "proposal", "handover", "verdict")

RULINGS_PASSING = ("SOUND",)
RULINGS_CONDITIONAL = ("FIX FIRST",)


class StateError(RuntimeError):
    """A state or gate precondition was not met."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_state(project: str, mode: str = "auto", max_usd: float = 25.0) -> Dict[str, Any]:
    if mode not in MODES:
        raise StateError(f"mode must be one of {', '.join(MODES)}")
    return {
        "schema_version": SCHEMA_VERSION,
        "project": project,
        "created_at": _now(),
        "updated_at": _now(),
        "mode": mode,
        "budget": {"max_usd": max_usd, "spent_usd": 0.0},
        "phases": {p: {"status": "not started", "artifacts": []} for p in PHASES},
        "gates": {g: {"status": "not started", "ruling": None, "round": 0,
                      "open_fixes": [], "decided_at": None} for g in GATES},
        "rounds": [],
        "resume_point": "run /ideate to begin",
    }


def state_path(directory: str | os.PathLike[str] = ".") -> Path:
    return Path(directory) / STATE_FILE


def load(directory: str | os.PathLike[str] = ".") -> Dict[str, Any]:
    path = state_path(directory)
    if not path.exists():
        raise StateError(f"no {STATE_FILE} in {Path(directory).resolve()}; run /pipeline init first")
    data = json.loads(path.read_text())
    if data.get("schema_version") != SCHEMA_VERSION:
        raise StateError(f"{path}: unsupported schema_version {data.get('schema_version')!r}")
    return data


def save(state: Dict[str, Any], directory: str | os.PathLike[str] = ".") -> Path:
    state["updated_at"] = _now()
    path = state_path(directory)
    path.write_text(json.dumps(state, indent=2) + "\n")
    return path


def set_mode(state: Dict[str, Any], mode: str) -> Dict[str, Any]:
    if mode not in MODES:
        raise StateError(f"mode must be one of {', '.join(MODES)}")
    state["mode"] = mode
    return state


def set_phase(state: Dict[str, Any], phase: str, status: str,
              artifacts: Optional[Iterable[str]] = None,
              reason: Optional[str] = None) -> Dict[str, Any]:
    if phase not in PHASES:
        raise StateError(f"unknown phase {phase!r}; expected one of {', '.join(PHASES)}")
    if status not in STATUSES:
        raise StateError(f"status must be one of {', '.join(STATUSES)}")
    entry = state["phases"][phase]
    entry["status"] = status
    if artifacts:
        for item in artifacts:
            if item not in entry["artifacts"]:
                entry["artifacts"].append(item)
    if status == "complete":
        entry["completed_at"] = _now()
        entry.pop("blocked_reason", None)
    if status == "blocked":
        entry["blocked_reason"] = reason or "unspecified"
    state["resume_point"] = describe_next(state)
    return state


def record_ruling(state: Dict[str, Any], gate: str, ruling: str, round_no: int,
                  open_fixes: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    if gate not in GATES:
        raise StateError(f"unknown gate {gate!r}; expected one of {', '.join(GATES)}")
    fixes = list(open_fixes or [])
    passing = ruling in RULINGS_PASSING or (ruling in RULINGS_CONDITIONAL and not fixes)
    state["gates"][gate] = {
        "status": "complete" if passing else "blocked",
        "ruling": ruling,
        "round": round_no,
        "open_fixes": fixes,
        "decided_at": _now(),
    }
    state["rounds"].append({"gate": gate, "round": round_no, "ruling": ruling,
                            "open_fixes": fixes, "at": _now()})
    state["resume_point"] = describe_next(state)
    return state


def gate_passed(state: Dict[str, Any], gate: str) -> bool:
    """A gate passes only on a recorded ruling: SOUND, or FIX FIRST with no fix left open."""
    if gate not in GATES:
        raise StateError(f"unknown gate {gate!r}")
    record = state["gates"][gate]
    if record["status"] != "complete":
        return False
    ruling = record.get("ruling")
    if ruling in RULINGS_PASSING:
        return True
    return ruling in RULINGS_CONDITIONAL and not record.get("open_fixes")


def add_spend(state: Dict[str, Any], usd: float) -> Dict[str, Any]:
    if usd < 0:
        raise StateError("spend must not be negative")
    state["budget"]["spent_usd"] = round(state["budget"]["spent_usd"] + usd, 4)
    return state


def budget_exceeded(state: Dict[str, Any]) -> bool:
    budget = state["budget"]
    return budget["spent_usd"] >= budget["max_usd"]


def next_phase(state: Dict[str, Any]) -> Optional[str]:
    """The first phase that is not complete, or None when every phase is done."""
    for phase in PHASES:
        if state["phases"][phase]["status"] != "complete":
            return phase
    return None


def should_pause_after(state: Dict[str, Any], phase: str) -> bool:
    mode = state["mode"]
    if mode == "manual":
        return True
    if mode == "yolo":
        return False
    return phase in AUTO_CHECKPOINTS


def blockers(state: Dict[str, Any], phase: str) -> List[str]:
    """Why `phase` may not run yet. Empty means it may."""
    if phase not in PHASES:
        raise StateError(f"unknown phase {phase!r}")
    reasons: List[str] = []
    index = PHASES.index(phase)
    own = state["phases"][phase]
    if own["status"] == "blocked":
        reasons.append(f"{phase} is blocked: {own.get('blocked_reason', 'unspecified')}")
    for earlier in PHASES[:index]:
        entry = state["phases"][earlier]
        if entry["status"] != "complete":
            reasons.append(f"{earlier} is {entry['status']}, not complete")
    gate = GATED_BY.get(phase)
    if gate and not gate_passed(state, gate):
        record = state["gates"][gate]
        detail = record.get("ruling") or "no ruling recorded"
        if record.get("open_fixes"):
            detail = f"{detail} with {len(record['open_fixes'])} fix(es) still open"
        reasons.append(f"{gate} gate has not passed ({detail})")
    if budget_exceeded(state):
        budget = state["budget"]
        reasons.append(f"budget exceeded: spent ${budget['spent_usd']} of ${budget['max_usd']}")
    return reasons


def describe_next(state: Dict[str, Any]) -> str:
    phase = next_phase(state)
    if phase is None:
        return "all phases complete"
    reasons = blockers(state, phase)
    if reasons:
        return f"blocked before /{phase}: " + "; ".join(reasons)
    return f"run /{phase}"


# --------------------------------------------------------------------------- registry

def registry_load() -> Dict[str, Any]:
    path = registry_path()
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "projects": []}
    return json.loads(path.read_text())


def registry_upsert(state: Dict[str, Any], project_dir: str | os.PathLike[str]) -> Path:
    """Record this project in the user-level registry the tracker page reads."""
    data = registry_load()
    row = {
        "project": state["project"],
        "path": str(Path(project_dir).resolve()),
        "phase": next_phase(state) or "complete",
        "mode": state["mode"],
        "judge_ruling": state["gates"]["judge"].get("ruling"),
        "launched": state["phases"]["launch"]["status"] == "complete",
        "updated_at": state["updated_at"],
    }
    rows = [r for r in data["projects"] if r.get("path") != row["path"]]
    data["projects"] = sorted(rows + [row], key=lambda r: r["updated_at"], reverse=True)
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


# --------------------------------------------------------------------------- CLI

def _emit(data: Any) -> None:
    print(json.dumps(data, indent=2))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="state.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-C", "--dir", default=".", help="project directory (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create pipeline.json")
    p.add_argument("--project", required=True)
    p.add_argument("--mode", default="auto", choices=MODES)
    p.add_argument("--max-usd", type=float, default=25.0)

    sub.add_parser("show", help="print the whole state")
    sub.add_parser("next", help="print the next phase and whether it is runnable")

    p = sub.add_parser("mode", help="get or set the run mode")
    p.add_argument("value", nargs="?", choices=MODES)

    p = sub.add_parser("phase", help="set a phase's status")
    p.add_argument("name", choices=PHASES)
    p.add_argument("status", choices=STATUSES)
    p.add_argument("--artifact", action="append", default=[])
    p.add_argument("--reason")

    p = sub.add_parser("ruling", help="record a gate ruling")
    p.add_argument("gate", choices=GATES)
    p.add_argument("--ruling", required=True)
    p.add_argument("--round", type=int, default=1)
    p.add_argument("--open-fix", action="append", default=[])

    p = sub.add_parser("budget", help="inspect or adjust the budget")
    p.add_argument("--add", type=float)
    p.add_argument("--max", type=float)

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            if state_path(args.dir).exists():
                raise StateError(f"{STATE_FILE} already exists in {Path(args.dir).resolve()}")
            state = new_state(args.project, args.mode, args.max_usd)
            save(state, args.dir)
            registry_upsert(state, args.dir)
            _emit({"created": str(state_path(args.dir)), "next": describe_next(state)})
            return 0

        state = load(args.dir)

        if args.command == "show":
            _emit(state)
            return 0
        if args.command == "next":
            phase = next_phase(state)
            _emit({"phase": phase, "runnable": phase is not None and not blockers(state, phase),
                   "blockers": blockers(state, phase) if phase else [],
                   "pause_after": should_pause_after(state, phase) if phase else False,
                   "mode": state["mode"], "resume_point": describe_next(state)})
            return 0
        if args.command == "mode":
            if args.value:
                set_mode(state, args.value)
                save(state, args.dir)
            _emit({"mode": state["mode"]})
            return 0
        if args.command == "phase":
            set_phase(state, args.name, args.status, args.artifact, args.reason)
            save(state, args.dir)
            registry_upsert(state, args.dir)
            _emit({"phase": args.name, "status": args.status, "next": describe_next(state)})
            return 0
        if args.command == "ruling":
            record_ruling(state, args.gate, args.ruling, args.round, args.open_fix)
            save(state, args.dir)
            registry_upsert(state, args.dir)
            _emit({"gate": args.gate, "passed": gate_passed(state, args.gate),
                   "next": describe_next(state)})
            return 0
        if args.command == "budget":
            if args.max is not None:
                state["budget"]["max_usd"] = args.max
            if args.add is not None:
                add_spend(state, args.add)
            if args.max is not None or args.add is not None:
                save(state, args.dir)
            _emit({**state["budget"], "exceeded": budget_exceeded(state)})
            return 0
    except StateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
