#!/usr/bin/env python3
"""Judge panel keys for Project Kit: see what the panel is missing, and store a key safely.

    keys.py status            seats filled, which are keys, what is missing, what to ask for
    keys.py add <family>      store that family's API key in the credentials file
                              (prompted with input hidden; or piped on stdin with --stdin)
    keys.py paste-rest        fill every seat still empty with a paste seat
    keys.py remove <family>   delete that family's key from the credentials file

Keys live in ~/.claude/project-kit/.env (mode 600, directory 700), never in a project or
the plugin repository: both are git repositories, and the plugin's is public. A key is
never printed, logged or passed on a command line.

Exit codes: 0 done (status: the panel can sit), 1 refused or the panel is still short,
2 usage error.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import doctor  # noqa: E402

# The env name `add` writes for each family. Any alias in doctor.FAMILY_BY_KEY still counts
# when it is already set; this is only the name a new key is stored under.
KEY_BY_FAMILY: Dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "google": "GEMINI_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
    "xai": "XAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}
# Order paste-rest fills empty seats in: families whose chat apps are free to use first.
PASTE_ORDER = ("google", "moonshot", "openai", "deepseek", "mistral", "xai")
MIN_KEY_LENGTH = 16


def env_file() -> Path:
    return doctor.ENV_FILE


def read_lines(path: Path) -> List[str]:
    return path.read_text().splitlines() if path.exists() else []


def write_private(path: Path, lines: List[str]) -> None:
    """Replace `path` with `lines`, readable by the owner only, without a window in which
    the file exists with wider permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass  # a directory we do not own; the file itself is still 600
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".env.")
    try:
        os.chmod(tmp, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write("\n".join(lines) + ("\n" if lines else ""))
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def set_value(lines: List[str], name: str, value: Optional[str]) -> List[str]:
    """`lines` with `name` set to `value` (or removed when None); other lines kept as is."""
    out = [line for line in lines
           if line.strip().partition("=")[0].strip() != name]
    if value is not None:
        out.append(f"{name}={value}")
    return out


def check_key(family: str, key: str) -> Optional[str]:
    """Why `key` cannot be stored for `family`, or None."""
    if not key:
        return "no key was given"
    if any(c.isspace() for c in key) or key.partition("=")[0] in doctor.FAMILY_BY_KEY:
        return "that does not look like a bare API key (paste the key only, no name or spaces)"
    if len(key) < MIN_KEY_LENGTH:
        return f"that is {len(key)} characters; API keys are at least {MIN_KEY_LENGTH}"
    if key.startswith("sk-ant-"):
        return "that is an Anthropic key; Anthropic wrote the plan and cannot judge it"
    return None


def refresh_cache() -> None:
    """Re-check the panel now, so the next gate sees the new key instead of a cached
    'not ready' for up to a day."""
    panel = doctor.check_panel()
    try:
        data = json.loads(doctor.CACHE.read_text()) if doctor.CACHE.exists() else {}
    except (json.JSONDecodeError, OSError):
        data = {}
    checks = [c for c in data.get("checks", []) if c.get("name") != panel.name]
    checks.append({"name": panel.name, "ok": panel.ok, "required": panel.required,
                   "detail": panel.detail, "fix": panel.fix})
    data.setdefault("checked_at", time.time())
    data["checks"] = checks
    try:
        doctor.CACHE.parent.mkdir(parents=True, exist_ok=True)
        doctor.CACHE.write_text(json.dumps(data, indent=2))
    except OSError:
        pass


def status() -> Dict[str, object]:
    env = doctor.load_panel_env()
    families, notes, problems = doctor.panel_seats(env)
    pasted = [f for f in families if any(n.startswith(f"{f}: paste ") for n in notes)]
    keyed = [f for f in families if f not in pasted]
    missing = max(0, doctor.SEATS_REQUIRED - len(families))
    if missing == 0:
        ask = None
    elif not keyed:
        ask = "at least one judge key (pk keys add <family>), then pk keys paste-rest"
    else:
        ask = (f"{missing} more seat(s): another family's key (pk keys add <family>), "
               "or pk keys paste-rest")
    return {
        "env_file": str(env_file()),
        "seats_required": doctor.SEATS_REQUIRED,
        "seats_filled": len(families),
        "families": families,
        "key_seats": keyed,
        "paste_seats": pasted,
        "missing": missing,
        "has_key_seat": bool(keyed),
        "ready": missing == 0 and not problems,
        "addable": [f for f in KEY_BY_FAMILY if f not in families],
        "ask": ask,
        "problems": problems,
    }


def add(family: str, from_stdin: bool, live: bool) -> int:
    family = family.lower()
    if family == doctor.EXCLUDED_FAMILY:
        print(f"refused: {family} wrote the plan and cannot hold a judge seat", file=sys.stderr)
        return 1
    if family not in KEY_BY_FAMILY:
        print(f"unknown family {family!r}; one of: {', '.join(KEY_BY_FAMILY)}",
              file=sys.stderr)
        return 2
    name = KEY_BY_FAMILY[family]
    if from_stdin or not sys.stdin.isatty():
        key = sys.stdin.readline().strip()
    else:
        key = getpass.getpass(f"{name} (input hidden): ").strip()
    why = check_key(family, key)
    if why:
        print(f"refused: {why}. Nothing was stored.", file=sys.stderr)
        return 1
    path = env_file()
    write_private(path, set_value(read_lines(path), name, key))
    refresh_cache()
    result: Dict[str, object] = {"stored": name, "length": len(key), "env_file": str(path)}
    if live:
        ok, why = doctor.probe_seat(family, doctor.load_panel_env())
        result["probe"] = {"ok": ok, "detail": why}
    result["panel"] = status()
    print(json.dumps(result, indent=2))
    return 0


def remove(family: str) -> int:
    family = family.lower()
    if family not in KEY_BY_FAMILY:
        print(f"unknown family {family!r}; one of: {', '.join(KEY_BY_FAMILY)}",
              file=sys.stderr)
        return 2
    path = env_file()
    if path.exists():
        write_private(path, set_value(read_lines(path), KEY_BY_FAMILY[family], None))
    refresh_cache()
    print(json.dumps({"removed": KEY_BY_FAMILY[family], "panel": status()}, indent=2))
    return 0


def paste_rest() -> int:
    env = doctor.load_panel_env()
    families, _, _ = doctor.panel_seats(env)
    missing = doctor.SEATS_REQUIRED - len(families)
    pasted = doctor.paste_families(env)
    added = [f for f in PASTE_ORDER if f not in families][:max(0, missing)]
    if added:
        path = env_file()
        write_private(path, set_value(read_lines(path), doctor.PASTE_SEATS_KEY,
                                      ",".join(pasted + added)))
        refresh_cache()
    print(json.dumps({"paste_seats_added": added, "panel": status()}, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="keys.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="what the panel has and what it is missing")
    p = sub.add_parser("add", help="store one family's API key (input hidden)")
    p.add_argument("family", help=", ".join(KEY_BY_FAMILY))
    p.add_argument("--stdin", action="store_true",
                   help="read the key from stdin instead of prompting")
    p.add_argument("--live", action="store_true",
                   help="after storing, probe the seat with a tiny real call")
    sub.add_parser("paste-rest", help="fill every empty seat with a paste seat")
    p = sub.add_parser("remove", help="delete one family's stored key")
    p.add_argument("family")
    args = parser.parse_args(argv)

    if args.cmd == "status":
        report = status()
        print(json.dumps(report, indent=2))
        return 0 if report["ready"] else 1
    if args.cmd == "add":
        return add(args.family, args.stdin, args.live)
    if args.cmd == "remove":
        return remove(args.family)
    return paste_rest()


if __name__ == "__main__":
    sys.exit(main())
