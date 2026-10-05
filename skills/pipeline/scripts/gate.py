#!/usr/bin/env python3
"""Gate checks for Project Kit. Exits non-zero so a skill refuses rather than proceeds.

    gate.py phase design         may /design run here?
    gate.py gate judge           has the judge gate passed?
    gate.py harness              is the harness allowlisted for an unattended yolo run?

Exit codes: 0 pass, 1 refused (reasons on stderr), 2 usage or state error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import state  # noqa: E402

# Tool permissions an unattended run needs. Absence does not break yolo; it means the run
# will stop on a permission prompt, which the user must be told rather than discover.
NEEDED_PERMISSIONS = ("Bash", "Edit", "Write")
SETTINGS = Path(os.path.expanduser(
    os.environ.get("PROJECT_KIT_SETTINGS", "~/.claude/settings.json")))


def _refuse(reasons: List[str]) -> int:
    print("REFUSED", file=sys.stderr)
    for reason in reasons:
        print(f"  - {reason}", file=sys.stderr)
    return 1


def allowlist_gaps() -> List[str]:
    """Permission prefixes with no `allow` entry in settings.json."""
    if not SETTINGS.exists():
        return list(NEEDED_PERMISSIONS)
    try:
        allow = json.loads(SETTINGS.read_text()).get("permissions", {}).get("allow", [])
    except (json.JSONDecodeError, AttributeError):
        return list(NEEDED_PERMISSIONS)
    return [need for need in NEEDED_PERMISSIONS
            if not any(str(rule).split("(")[0].strip() == need for rule in allow)]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="gate.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-C", "--dir", default=".", help="project directory (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("phase", help="may this phase run?")
    p.add_argument("name", choices=state.PHASES)

    p = sub.add_parser("gate", help="has this gate passed?")
    p.add_argument("name", choices=state.GATES)

    sub.add_parser("harness", help="report harness allowlist readiness for yolo")

    args = parser.parse_args(argv)

    if args.command == "harness":
        gaps = allowlist_gaps()
        print(json.dumps({
            "settings": str(SETTINGS),
            "settings_exists": SETTINGS.exists(),
            "missing_allow": gaps,
            "unattended_ready": not gaps,
            "note": ("yolo will run without stopping at Project Kit checkpoints, but Claude "
                     "Code will still prompt for the permissions listed in missing_allow")
                    if gaps else "no Project Kit checkpoints and no expected permission prompts",
        }, indent=2))
        return 0

    try:
        current = state.load(args.dir)
    except state.StateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.command == "phase":
        reasons = state.blockers(current, args.name)
        if reasons:
            return _refuse(reasons)
        print(json.dumps({"phase": args.name, "runnable": True,
                          "pause_after": state.should_pause_after(current, args.name),
                          "mode": current["mode"]}, indent=2))
        return 0

    if args.command == "gate":
        if not state.gate_passed(current, args.name):
            record = current["gates"][args.name]
            detail = record.get("ruling") or "no ruling recorded"
            reasons = [f"{args.name} gate has not passed ({detail})"]
            reasons += [f"open fix: {fix}" for fix in record.get("open_fixes", [])]
            return _refuse(reasons)
        print(json.dumps({"gate": args.name, "passed": True,
                          "ruling": current["gates"][args.name]["ruling"]}, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
