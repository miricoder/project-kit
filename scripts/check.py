#!/usr/bin/env python3
"""Run locally exactly what CI runs, in the same order.

Without this the only way to know a change is safe is to push and wait. The steps mirror
.github/workflows/ci.yml one for one; if that file changes, change this and the test that
pins them together.

    pk check            run every check
    pk check --fix      regenerate stale docs instead of only reporting them
    pk check --json     machine-readable

Exit codes: 0 everything required passed, 1 something failed, 2 usage error. The same
contract as gate.py and doctor.py, so this can gate a script or a git hook.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from doctor import Check, render, run  # noqa: E402 - shared report format, not duplicated

# Mirrors .github/workflows/ci.yml. tests/test_check.py asserts these stay in step.
TEST_COMMAND = (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".")
DOCS_COMMAND = (sys.executable, "docs/build_docs.py", "--check")
DOCS_FIX_COMMAND = (sys.executable, "docs/build_docs.py")


def _tail(text: str, lines: int = 12) -> List[str]:
    return [line for line in (text or "").strip().splitlines()[-lines:] if line.strip()]


def run_tests() -> Check:
    code, out = run(TEST_COMMAND, timeout=300)
    if code == 0:
        ran = next((line for line in out.splitlines() if line.startswith("Ran ")), "ran")
        return Check("Unit tests", True, ran.strip())
    return Check("Unit tests", False, "failed",
                 fix="python3 -m unittest discover -s tests -t . -v",
                 notes=_tail(out))


def check_docs(fix: bool = False) -> Check:
    code, out = run(DOCS_COMMAND, timeout=120)
    if code == 0:
        return Check("Docs up to date", True, "generated pages match their sources")
    if not fix:
        return Check("Docs up to date", False, "generated pages are stale",
                     fix="pk check --fix   (or: python3 docs/build_docs.py)",
                     notes=_tail(out, 4))
    code, out = run(DOCS_FIX_COMMAND, timeout=120)
    if code != 0:
        return Check("Docs up to date", False, "regeneration failed", notes=_tail(out))
    return Check("Docs up to date", True, "regenerated — commit the changes",
                 notes=_tail(out, 4))


def validate_plugin() -> Check:
    """Degrades to a warning rather than a failure when no plugin-capable CLI exists, so
    `pk check` still works on a bare machine. CI always has one."""
    claude = shutil.which("claude")
    if not claude:
        return Check("Plugin manifests", False, "skipped — no claude CLI on PATH",
                     required=False,
                     fix="install Claude Code, then: claude plugin validate . --strict")
    code, out = run([claude, "plugin", "validate", str(ROOT), "--strict"], timeout=120)
    if code == 0:
        return Check("Plugin manifests", True, "validate --strict passed")
    if "unknown command" in out.lower() or "usage: claude" in out.lower():
        return Check("Plugin manifests", False,
                     "skipped — this claude build has no `plugin` command", required=False,
                     fix="npm i -g @anthropic-ai/claude-code@latest")
    return Check("Plugin manifests", False, "validate --strict failed",
                 fix="claude plugin validate . --strict", notes=_tail(out))


def collect(fix: bool = False) -> List[Check]:
    """Order matters: it is the order CI runs them, so the first failure a user sees
    locally is the first one they would have seen in CI."""
    return [run_tests(), check_docs(fix), validate_plugin()]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="check.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fix", action="store_true", help="regenerate stale docs")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args(argv)

    checks = collect(fix=args.fix)
    if args.json:
        print(json.dumps({"checks": [
            {"name": c.name, "ok": c.ok, "required": c.required, "status": c.status,
             "detail": c.detail, "notes": c.notes} for c in checks]}, indent=2))
    else:
        print(render(checks, title="Project Kit — repository checks (same as CI)",
                     success="Safe to commit and push."))
    return 1 if any(not c.ok and c.required for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
