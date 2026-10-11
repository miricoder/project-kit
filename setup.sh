#!/bin/sh
# Project Kit environment setup (macOS, Linux, and any POSIX shell incl. Git Bash).
#
# Deliberately thin: it locates a Python 3 and hands off to scripts/doctor.py, which holds
# all the logic and is unit-tested. setup.ps1 does the same on Windows, so both platforms
# run identical checks rather than two shell implementations that drift apart.
#
#   ./setup.sh              report what is missing
#   ./setup.sh --fix        apply the safe fixes
#   ./setup.sh --dev        development install (symlink this repo into ~/.claude/skills)
#   ./setup.sh --live       also probe each judge seat with a real call
set -eu

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DOCTOR="$DIR/scripts/doctor.py"

[ -f "$DOCTOR" ] || { echo "error: $DOCTOR not found" >&2; exit 2; }

PY=""
for candidate in python3 python py; do
  command -v "$candidate" >/dev/null 2>&1 || continue
  if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 9) else 1)' 2>/dev/null; then
    PY="$candidate"
    break
  fi
done

if [ -z "$PY" ]; then
  echo "error: Python 3.9+ is required and was not found." >&2
  echo "  tried: python3, python, py" >&2
  echo "  install from https://www.python.org/downloads/" >&2
  exit 1
fi

exec "$PY" "$DOCTOR" "$@"
