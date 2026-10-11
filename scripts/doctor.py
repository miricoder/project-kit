#!/usr/bin/env python3
"""Environment doctor for Project Kit.

Checks everything the pipeline needs before it runs, on macOS, Linux and Windows.
`setup.sh` and `setup.ps1` are thin wrappers around this module, so both platforms run
identical, tested logic rather than two shell implementations that drift.

    doctor.py              report only (default)
    doctor.py --fix        perform the safe fixes
    doctor.py --dev        development install: symlink this repo into ~/.claude/skills
    doctor.py --live       probe each judge seat with a real call
    doctor.py --json       machine-readable report

Exit codes: 0 all required checks pass, 1 something required is missing, 2 usage error.
The same contract as gate.py, so a wrapper can branch on it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
REPO_SLUG = "miricoder/project-kit"
PLUGIN_NAME = "project-kit"
SKILLS_LINK = Path(os.path.expanduser("~/.claude/skills")) / PLUGIN_NAME

MIN_PYTHON = (3, 9)
MIN_CLAUDE = (2, 0, 0)

# Credential env names mapped to the model family they belong to. The panel rule is three
# DISTINCT families, so two keys from one family fill one seat, not two.
FAMILY_BY_KEY: Dict[str, str] = {
    "MOONSHOT_API_KEY": "moonshot",
    "KIMI_API_KEY": "moonshot",
    "GEMINI_API_KEY": "google",
    "GOOGLE_API_KEY": "google",
    "OPENAI_API_KEY": "openai",
    "XAI_API_KEY": "xai",
    "GROK_API_KEY": "xai",
    "DEEPSEEK_API_KEY": "deepseek",
    "MISTRAL_API_KEY": "mistral",
    "COHERE_API_KEY": "cohere",
    "ANTHROPIC_API_KEY": "anthropic",
}
# Claude authors the plan, so Claude cannot judge it: a judge from the authoring family
# shares its priors. Recorded here, enforced by the panel.
EXCLUDED_FAMILY = "anthropic"
SEATS_REQUIRED = 3

ENV_FILE = Path(os.path.expanduser(
    os.environ.get("PROJECT_KIT_ENV", "~/.claude/project-kit/.env")))

_VERSION = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True
    fix: Optional[str] = None          # command the user can run
    notes: List[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.ok:
            return "pass"
        return "FAIL" if self.required else "warn"


# --------------------------------------------------------------------------- helpers

def parse_version(text: str) -> Optional[Tuple[int, int, int]]:
    """First dotted version in `text`, as a 3-tuple. None when there is none."""
    match = _VERSION.search(text or "")
    if not match:
        return None
    major, minor, patch = match.group(1), match.group(2), match.group(3)
    return (int(major), int(minor), int(patch or 0))


def run(argv: Sequence[str], timeout: float = 20.0) -> Tuple[int, str]:
    """Run a command, returning (exit code, stdout+stderr). Never raises."""
    try:
        done = subprocess.run(list(argv), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def parse_env_file(text: str) -> Dict[str, str]:
    """KEY=VALUE lines; `#` comments and blanks ignored. Values are not unquoted beyond
    stripping one matching pair, which is all a credentials file needs."""
    out: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key.strip()] = value
    return out


# --------------------------------------------------------------------------- checks

def find_python() -> Check:
    """Resolve a Python 3 interpreter. The running one counts first — doctor.py is already
    executing under it, so it is proven."""
    current = (sys.version_info.major, sys.version_info.minor)
    if current >= MIN_PYTHON:
        return Check("Python 3", True,
                     f"{sys.executable} ({current[0]}.{current[1]})")
    for name in ("python3", "python", "py"):
        path = shutil.which(name)
        if not path:
            continue
        code, out = run([path, "--version"])
        version = parse_version(out)
        if code == 0 and version and version[:2] >= MIN_PYTHON:
            return Check("Python 3", True, f"{path} ({version[0]}.{version[1]})")
    need = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    return Check("Python 3", False, f"need >= {need}, running {current[0]}.{current[1]}",
                 fix="install Python " + need + "+ from https://python.org/downloads")


def find_claude() -> Check:
    """Claude Code must be present *and* expose `plugin`. A 0.x/1.x build resolves fine and
    then has no plugin command at all, which is the trap this check exists to catch."""
    path = shutil.which("claude")
    if not path:
        return Check("Claude Code CLI", False, "not on PATH",
                     fix="npm i -g @anthropic-ai/claude-code@latest")
    code, out = run([path, "--version"])
    version = parse_version(out)
    shown = ".".join(str(p) for p in version) if version else "unknown"

    code, out = run([path, "plugin", "list"])
    supports = code == 0 and bool(re.search(r"plugin|marketplace|skills-dir", out, re.I))
    if supports:
        return Check("Claude Code CLI", True, f"{shown} at {path} (plugin supported)")

    notes = [f"`{path}` is {shown} and has no `plugin` subcommand."]
    real = Path(path).resolve()
    prefix_code, prefix_out = run(["npm", "config", "get", "prefix"])
    prefix = prefix_out.strip() if prefix_code == 0 else ""
    if prefix and prefix not in str(real):
        notes.append(
            f"It lives in {real.parent}, but your npm prefix is {prefix}. A plain "
            "`npm i -g` installs to the prefix and may lose the PATH race, leaving two "
            "installs. Remove the old one first.")
    return Check("Claude Code CLI", False, f"{shown} — no plugin support",
                 fix="npm i -g @anthropic-ai/claude-code@latest", notes=notes)


def check_git_identity() -> Check:
    missing = []
    for key in ("user.name", "user.email"):
        code, out = run(["git", "config", "--global", key])
        if code != 0 or not out.strip():
            missing.append(key)
    if not missing:
        _, name = run(["git", "config", "--global", "user.name"])
        _, mail = run(["git", "config", "--global", "user.email"])
        return Check("git identity", True, f"{name.strip()} <{mail.strip()}>")
    return Check("git identity", False, "unset: " + ", ".join(missing),
                 fix='git config --global user.name "Your Name" && '
                     'git config --global user.email "you@example.com"')


def installed_on_disk() -> Optional[str]:
    """Find the plugin on disk, independent of the CLI. Asking a broken CLI whether a
    plugin is installed yields a false negative, which is worse than not checking."""
    if SKILLS_LINK.exists():
        return "skills-dir symlink" if SKILLS_LINK.is_symlink() else "skills-dir"
    for base in (Path(os.path.expanduser("~/.claude/plugins")),):
        if (base / PLUGIN_NAME).exists() or list(base.glob(f"*/{PLUGIN_NAME}")):
            return "marketplace"
    return None


def check_plugin_installed(cli_ok: bool = True) -> Check:
    on_disk = installed_on_disk()
    if on_disk and not cli_ok:
        return Check("Plugin installed", True,
                     f"{PLUGIN_NAME} present ({on_disk}) — unverified, CLI too old",
                     notes=["fix the Claude Code CLI above, then `claude plugin list` "
                            "will confirm it loads"])
    if on_disk:
        path = shutil.which("claude")
        code, out = run([path, "plugin", "list"]) if path else (1, "")
        if code == 0 and PLUGIN_NAME in out:
            how = "skills-dir (development symlink)" if "skills-dir" in out else "marketplace"
            return Check("Plugin installed", True, f"{PLUGIN_NAME} via {how}, loaded")
        return Check("Plugin installed", False,
                     f"{PLUGIN_NAME} is on disk ({on_disk}) but the CLI does not load it",
                     fix="claude plugin list   # inspect, then re-add if absent")
    if not cli_ok:
        return Check("Plugin installed", False,
                     "not on disk, and the CLI is too old to install it",
                     fix="fix the Claude Code CLI above first")
    return Check("Plugin installed", False, f"{PLUGIN_NAME} not installed",
                 fix=f"claude plugin marketplace add {REPO_SLUG} && "
                     f"claude plugin install {PLUGIN_NAME}")


def panel_seats(env: Dict[str, str]) -> Tuple[List[str], List[str], List[str]]:
    """Return (families filled, notes, problems) for the judge panel.

    A CLI-backed seat counts without a key: a logged-in codex means the OpenAI seat is
    filled by subscription, no API key and no extra cost.
    """
    families: List[str] = []
    notes: List[str] = []
    problems: List[str] = []

    for key, value in sorted(env.items()):
        family = FAMILY_BY_KEY.get(key)
        if not family or not value:
            continue
        if family == EXCLUDED_FAMILY:
            problems.append(
                f"{key} is {EXCLUDED_FAMILY}, the authoring family — it cannot hold a "
                "judge seat and is not counted")
            continue
        if family in families:
            notes.append(f"{key} duplicates the {family} seat already filled")
            continue
        families.append(family)
        notes.append(f"{family}: {key}")

    if shutil.which("codex"):
        code, out = run(["codex", "login", "status"])
        if code == 0 and "logged in" in out.lower():
            if "openai" in families:
                notes.append("codex CLI also covers the openai seat (no key needed)")
            else:
                families.append("openai")
                notes.append("openai: codex CLI (subscription, no key)")

    if len(families) < SEATS_REQUIRED:
        problems.append(
            f"{len(families)} of {SEATS_REQUIRED} distinct families "
            f"({', '.join(families) or 'none'}) — the panel needs three, none anthropic")
    return families, notes, problems


# Minimal generate probes. A key that authenticates can still be out of credit, which
# is exactly how the moonshot seat looked healthy while being suspended.
LIVE_PROBES: Dict[str, Tuple[str, str, str]] = {
    "moonshot": ("https://api.moonshot.ai/v1/chat/completions", "MOONSHOT_API_KEY", "bearer"),
    "google": ("https://generativelanguage.googleapis.com/v1beta/models/"
               "gemini-flash-latest:generateContent", "GEMINI_API_KEY", "goog"),
    "openai": ("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY", "bearer"),
}


def classify(status: str, body: str) -> Tuple[str, str]:
    """(verdict, reason) from an HTTP status and response body.

    verdict is "ok", "billing", "auth", or "transient". The distinction matters: a 503 from
    an overloaded model must not be reported as a dead seat, while a 429 that says
    "insufficient balance" genuinely is one. Status alone cannot tell them apart, so the
    body is consulted.
    """
    if status == "200":
        return "ok", "generates"
    lowered = (body or "").lower()
    if any(word in lowered for word in
           ("balance", "credit", "billing", "exceeded your current quota", "suspended")):
        return "billing", "no credit or quota"
    if status in ("401", "403"):
        return "auth", f"rejected ({status})"
    if status in ("402",):
        return "billing", "payment required"
    if status in ("000", "408", "429", "500", "502", "503", "504"):
        return "transient", f"temporarily unavailable ({status})"
    return "auth", f"HTTP {status}"


def probe_seat(family: str, env: Dict[str, str], timeout: float = 30.0,
               attempts: int = 3) -> Tuple[bool, str]:
    """Attempt one tiny generation, retrying transient failures. Requires curl.

    Returns (counts_as_working, detail). A transient failure counts as working but says so:
    reporting a seat dead because a model was briefly overloaded would be worse than
    saying nothing.
    """
    spec = LIVE_PROBES.get(family)
    if not spec or not shutil.which("curl"):
        return True, "not probed"
    url, key_name, style = spec
    key = env.get(key_name) or os.environ.get(key_name, "")
    if not key:
        return True, "not probed (no key; CLI-backed)"
    if style == "goog":
        body = '{"contents":[{"parts":[{"text":"hi"}]}]}'
        headers = ["-H", f"x-goog-api-key: {key}"]
    else:
        model = "kimi-k2.6" if family == "moonshot" else "gpt-4o-mini"
        body = ('{"model":"%s","messages":[{"role":"user","content":"hi"}],'
                '"max_tokens":4}' % model)
        headers = ["-H", f"Authorization: Bearer {key}"]

    verdict, reason = "transient", "not attempted"
    for attempt in range(attempts):
        _, out = run(["curl", "-s", "-m", str(int(timeout)), "-o", "-",
                      "-w", "\n%{http_code}", url,
                      "-H", "Content-Type: application/json", *headers, "-d", body],
                     timeout=timeout + 5)
        text = (out or "").strip()
        status = text.rsplit("\n", 1)[-1] if text else "000"
        verdict, reason = classify(status, text)
        if verdict != "transient":
            break
        if attempt < attempts - 1:
            time.sleep(2 * (attempt + 1))
    if verdict == "ok":
        return True, reason
    if verdict == "transient":
        return True, f"{reason} — could not confirm, treating as available"
    return False, reason


def check_panel(live: bool = False) -> Check:
    env: Dict[str, str] = {}
    if ENV_FILE.exists():
        env.update(parse_env_file(ENV_FILE.read_text()))
    for key in FAMILY_BY_KEY:
        if os.environ.get(key):
            env.setdefault(key, os.environ[key])

    families, notes, problems = panel_seats(env)
    if live:
        working = []
        for family in families:
            ok, why = probe_seat(family, env)
            notes.append(f"{family}: {why}")
            if ok:
                working.append(family)
            else:
                problems.append(f"{family} is configured but cannot generate ({why})")
        families = working
        label = "working"
    else:
        label = "configured"
        notes.append("configured is not the same as working — re-run with --live to probe")
    detail = (f"{len(families)}/{SEATS_REQUIRED} seats {label}: "
              f"{', '.join(families) or 'none'}")
    if len(families) < SEATS_REQUIRED and not any("distinct families" in p for p in problems):
        problems.append(f"{len(families)} of {SEATS_REQUIRED} families usable")
    # Not required: /ideate through /design need no panel at all.
    return Check("Judge panel", not problems, detail, required=False,
                 fix=f"add a third family key to {ENV_FILE} (chmod 600)" if problems else None,
                 notes=notes + problems)


def check_allowlist() -> Check:
    sys.path.insert(0, str(ROOT / "skills" / "pipeline" / "scripts"))
    try:
        import gate  # noqa: WPS433 - resolved from the plugin's own scripts
    except ImportError:
        return Check("Unattended (yolo) allowlist", False, "gate.py not importable",
                     required=False)
    gaps = gate.allowlist_gaps()
    if not gaps:
        return Check("Unattended (yolo) allowlist", True, "configured", required=False)
    block = json.dumps(
        {"permissions": {"allow": ["Bash(python3:*)", "Bash(git:*)", "Bash(gh:*)",
                                   "Edit", "Write"]}}, indent=2)
    return Check("Unattended (yolo) allowlist", False,
                 "missing: " + ", ".join(gaps), required=False,
                 fix=f"add to {gate.SETTINGS}:\n{block}",
                 notes=["yolo still runs; Claude Code will just prompt for these"])


# --------------------------------------------------------------------------- fixes

def apply_dev_link() -> Check:
    """Symlink this repo into ~/.claude/skills so edits load live as <name>@skills-dir."""
    SKILLS_LINK.parent.mkdir(parents=True, exist_ok=True)
    if SKILLS_LINK.is_symlink() and SKILLS_LINK.resolve() == ROOT:
        return Check("Development symlink", True, f"{SKILLS_LINK} -> {ROOT}")
    if SKILLS_LINK.exists() and not SKILLS_LINK.is_symlink():
        return Check("Development symlink", False,
                     f"{SKILLS_LINK} exists and is not a symlink — refusing to replace it",
                     fix=f"remove {SKILLS_LINK} by hand, then re-run with --dev")
    if SKILLS_LINK.is_symlink():
        SKILLS_LINK.unlink()
    try:
        SKILLS_LINK.symlink_to(ROOT, target_is_directory=True)
    except OSError as exc:  # Windows without developer mode
        return Check("Development symlink", False, f"could not create symlink: {exc}",
                     fix="on Windows, enable Developer Mode or run as administrator")
    return Check("Development symlink", True, f"{SKILLS_LINK} -> {ROOT}")


def apply_git_identity(name: str, email: str) -> Check:
    run(["git", "config", "--global", "user.name", name])
    run(["git", "config", "--global", "user.email", email])
    return check_git_identity()


# --------------------------------------------------------------------------- report

def collect(dev: bool = False, live: bool = False) -> List[Check]:
    python_check, claude_check = find_python(), find_claude()
    checks = [python_check, claude_check, check_git_identity()]
    checks.append(apply_dev_link() if dev else check_plugin_installed(claude_check.ok))
    checks.extend([check_panel(live=live), check_allowlist()])
    return checks


def render(checks: Sequence[Check]) -> str:
    mark = {"pass": "[ ok ]", "warn": "[warn]", "FAIL": "[FAIL]"}
    width = max(len(c.name) for c in checks)
    lines = ["", "Project Kit — environment check", "=" * 34, ""]
    for check in checks:
        lines.append(f"{mark[check.status]}  {check.name:<{width}}  {check.detail}")
        for note in check.notes:
            lines.append(f"{'':8}{'':<{width}}  - {note}")
    failed = [c for c in checks if not c.ok and c.required]
    warned = [c for c in checks if not c.ok and not c.required]
    lines.append("")
    if failed:
        lines.append(f"{len(failed)} required check(s) failed. To fix:")
        for check in failed:
            lines.append(f"\n  {check.name}:\n    {check.fix or 'see notes above'}")
    else:
        lines.append("All required checks passed.")
        lines.append("Run `claude` then `/reload-plugins`, and start with `/ideate <your idea>`.")
    if warned:
        lines.append("")
        lines.append("Optional, not blocking:")
        for check in warned:
            lines.append(f"  {check.name}: {check.detail}")
            if check.fix:
                for fixline in check.fix.splitlines():
                    lines.append(f"    {fixline}")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- phase gate

# Environment requirements by phase. Everything a running skill has already proved — a
# working Python, an installed plugin — is deliberately absent: if gate.py is executing,
# those are true. Only what bites *later* is listed, so /ideate pays nothing and
# /handover pays for the panel check.
PHASE_REQUIREMENTS: Dict[str, Tuple[str, ...]] = {
    "handover": ("panel",),
    "verdict": ("panel",),
    "initiate": ("git",),
    "build": ("git",),
    "devops": ("git",),
    "test": ("git",),
    "security": ("git",),
    "launch": ("git",),
}

CACHE = Path(os.path.expanduser(
    os.environ.get("PROJECT_KIT_ENV_CACHE", "~/.claude/project-kit/environment.json")))
CACHE_TTL_SECONDS = 24 * 60 * 60


def _cached(name: str) -> Optional[dict]:
    """A recent result for one check, or None. Avoids paying for subprocess calls on
    every single gate invocation."""
    if not CACHE.exists():
        return None
    try:
        data = json.loads(CACHE.read_text())
        if time.time() - float(data.get("checked_at", 0)) > CACHE_TTL_SECONDS:
            return None
        return next((c for c in data.get("checks", []) if c.get("name") == name), None)
    except (json.JSONDecodeError, ValueError, OSError):
        return None


def cache_write(checks: Sequence[Check]) -> None:
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps({
            "checked_at": time.time(),
            "checks": [{"name": c.name, "ok": c.ok, "required": c.required,
                        "detail": c.detail, "fix": c.fix} for c in checks]}, indent=2))
    except OSError:
        pass  # a read-only home must not break the pipeline


def environment_blockers(phase: str) -> Tuple[List[str], List[str]]:
    """(blockers, advisories) for `phase`.

    Blockers are environment problems that make this phase impossible. Advisories are
    problems that will bite a later phase — surfaced early so a short judge panel is
    discovered at /ideate rather than three phases in.
    """
    needed = PHASE_REQUIREMENTS.get(phase, ())
    blockers: List[str] = []

    if "git" in needed:
        cached = _cached("git identity")
        check = check_git_identity() if cached is None else Check(
            "git identity", cached["ok"], cached["detail"], fix=cached.get("fix"))
        if not check.ok:
            blockers.append(f"git identity {check.detail} — needed to commit. Fix: {check.fix}")

    if "panel" in needed:
        cached = _cached("Judge panel")
        check = check_panel() if cached is None else Check(
            "Judge panel", cached["ok"], cached["detail"], required=False,
            fix=cached.get("fix"))
        if not check.ok:
            blockers.append(f"judge panel: {check.detail}. Fix: {check.fix}")

    advisories: List[str] = []
    if phase not in ("handover", "verdict"):
        panel = _cached("Judge panel")
        if panel and not panel["ok"]:
            advisories.append(
                f"judge panel is not ready ({panel['detail']}) — /handover will refuse. "
                "Run `pk doctor --live` to check the seats.")
    return blockers, advisories


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="doctor.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fix", action="store_true", help="apply the safe fixes")
    parser.add_argument("--dev", action="store_true",
                        help="development install: symlink this repo into ~/.claude/skills")
    parser.add_argument("--live", action="store_true",
                        help="probe each judge seat with a tiny real call (costs a few tokens)")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args(argv)

    if args.fix and not args.dev:
        identity = check_git_identity()
        if not identity.ok and sys.stdin.isatty():
            print("git identity is unset and is needed for commits.")
            name = input("  git user.name:  ").strip()
            email = input("  git user.email: ").strip()
            if name and email:
                apply_git_identity(name, email)

    checks = collect(dev=args.dev, live=args.live)
    cache_write(checks)
    if args.json:
        print(json.dumps({"checks": [
            {"name": c.name, "ok": c.ok, "required": c.required, "status": c.status,
             "detail": c.detail, "fix": c.fix, "notes": c.notes} for c in checks]}, indent=2))
    else:
        print(render(checks))
    return 1 if any(not c.ok and c.required for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
