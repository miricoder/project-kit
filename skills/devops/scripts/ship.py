#!/usr/bin/env python3
"""Shipping for Project Kit: the mechanical half of /devops, /test, /security and /launch.

    ship.py config --target cloudrun --health /v1/health [--env NAME ...]
    ship.py status                         what is configured, deployed and recorded
    ship.py smoke <url>                    is the deployment up? (health path answers 200)
    ship.py record <staging|production> --url <url> [--version <v>] [--kind deploy|rollback|restore]
    ship.py release <tag>                  tag HEAD as a release (refuses unless it is ready)
    ship.py done devops                    CI, a release and a working staging deploy
    ship.py test                           the test gate: full suite + every scenario mapped
    ship.py audit                          the security gate: secrets, dependencies, threat model
    ship.py done launch                    production up, gates passed, rollback rehearsed

Deploying itself (gcloud, fly, a Docker host) is done by the skill with the user's own
accounts. What is recorded here is checked here: a deploy is recorded only after this
script reaches it, a gate only after this script ran it. State lives in pipeline.json under
"ship"; older state files load unchanged.

Exit codes: 0 ok, 1 refused (reasons on stderr), 2 usage or state error.
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
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "pipeline" / "scripts"))
sys.path.insert(0, str(HERE.parents[2] / "build" / "scripts"))
sys.path.insert(0, str(HERE.parents[3] / "scripts"))

import slices  # noqa: E402
import state  # noqa: E402
from qa import FEATURE, scenarios  # noqa: E402

TARGETS = ("cloudrun", "fly", "render", "docker", "other")
ENVS = ("staging", "production")
KINDS = ("deploy", "rollback", "restore")
SMOKE_TIMEOUT = 15
TEST_REPORT = "docs/test-report.md"
AUDIT_REPORT = "docs/security-audit.md"
THREAT_MODEL = "docs/threat-model.md"
THREAT_SECTIONS = ("Assets", "Threats", "Mitigations")
CI_FILES = (".github/workflows", ".gitlab-ci.yml", ".circleci/config.yml",
            "bitbucket-pipelines.yml")

# High-signal secret shapes only: a noisy scanner gets ignored, and then it guards nothing.
SECRET_PATTERNS = {
    "Anthropic API key": r"sk-ant-[A-Za-z0-9_\-]{20,}",
    "OpenAI API key": r"sk-(?:proj-)?[A-Za-z0-9]{32,}",
    "AWS access key": r"\bAKIA[0-9A-Z]{16}\b",
    "GitHub token": r"\bgh[pousr]_[A-Za-z0-9]{36,}\b",
    "Slack token": r"\bxox[abprs]-[A-Za-z0-9\-]{10,}",
    "Google API key": r"\bAIza[0-9A-Za-z_\-]{35}\b",
    "private key": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "password in a URL": r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:[^\s@/]{6,}@(?!localhost|127\.0\.0\.1)",
}
SECRET_RE = re.compile("|".join(f"(?P<g{i}>{p})" for i, p in enumerate(SECRET_PATTERNS.values())))


class ShipError(RuntimeError):
    """A shipping precondition was not met."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- state

def ship(st: Dict[str, Any]) -> Dict[str, Any]:
    return st.setdefault("ship", {"deploys": []})


def deploys(st: Dict[str, Any], env: Optional[str] = None) -> List[Dict[str, Any]]:
    return [d for d in ship(st).get("deploys", []) if env is None or d["env"] == env]


def latest(st: Dict[str, Any], env: str, kind: str = "deploy") -> Optional[Dict[str, Any]]:
    found = [d for d in deploys(st, env) if d["kind"] == kind]
    return found[-1] if found else None


# --------------------------------------------------------------------------- git

def git(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=project, capture_output=True, text=True)


def head(project: Path, short: bool = True) -> Optional[str]:
    out = git(project, "rev-parse", *(["--short"] if short else []), "HEAD")
    return out.stdout.strip() if out.returncode == 0 else None


# Files this kit writes as it records; a change to them is not uncommitted work.
OWN_FILES = (state.STATE_FILE, TEST_REPORT, AUDIT_REPORT)


def dirty(project: Path) -> List[str]:
    out = git(project, "status", "--porcelain")
    if out.returncode != 0:
        return ["not a git repository"]
    return [line for line in out.stdout.splitlines()
            if line.strip() and line[3:].strip() not in OWN_FILES]


def commit_of(project: Path, ref: str) -> Optional[str]:
    out = git(project, "rev-parse", "--short", f"{ref}^{{commit}}")
    return out.stdout.strip() if out.returncode == 0 else None


def same_commit(project: Path, a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b:
        return False
    ca, cb = commit_of(project, a) or a, commit_of(project, b) or b
    return ca.startswith(cb) or cb.startswith(ca)


# --------------------------------------------------------------------------- checks

def smoke(url: str, health: str = "/") -> Dict[str, Any]:
    """GET the health path. Up means HTTP 200 within the timeout."""
    target = url.rstrip("/") + (health if health.startswith("/") else "/" + health)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(urllib.request.Request(
                target, headers={"User-Agent": "project-kit-smoke"}), timeout=SMOKE_TIMEOUT) as r:
            status, body = r.status, r.read(400).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status, body = exc.code, ""
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"url": target, "ok": False, "status": None, "error": str(exc)}
    return {"url": target, "ok": status == 200, "status": status,
            "ms": round((time.monotonic() - started) * 1000), "body": body.strip()[:200]}


def ci_files(project: Path) -> List[Path]:
    found: List[Path] = []
    for name in CI_FILES:
        path = project / name
        if path.is_dir():
            found += sorted(p for p in path.iterdir() if p.suffix in (".yml", ".yaml"))
        elif path.is_file():
            found.append(path)
    return found


def ci_blockers(project: Path, st: Dict[str, Any]) -> List[str]:
    command = slices.build_config(st).get("test_command")
    files = ci_files(project)
    if not files:
        return ["no CI configuration (.github/workflows/*.yml or equivalent)"]
    if command and not any(command in f.read_text(encoding="utf-8", errors="replace")
                           for f in files):
        return [f"no CI file runs the project's test command `{command}`"]
    return []


DEPENDENCY_UPDATERS = (".github/dependabot.yml", ".github/dependabot.yaml", "renovate.json",
                       ".github/renovate.json", "renovate.json5")


def upkeep_blockers(project: Path) -> List[str]:
    """Iterations keep shipping without a person: CI deploys staging when the tests pass,
    and a bot proposes dependency updates."""
    reasons: List[str] = []
    texts = [f.read_text(encoding="utf-8", errors="replace").lower() for f in ci_files(project)]
    if not any("deploy" in t and "staging" in t for t in texts):
        reasons.append("no CI job deploys to staging after the tests pass "
                       "(references/targets.md, 'Continuous deploy')")
    if not any((project / name).is_file() for name in DEPENDENCY_UPDATERS):
        reasons.append("no dependency updates configured (.github/dependabot.yml)")
    return reasons


def https_required(url: str) -> List[str]:
    if os.environ.get("PROJECT_KIT_ALLOW_HTTP") == "1":
        return []
    return [] if urlparse(url).scheme == "https" else [f"production must be https: {url}"]


def scan_secrets(project: Path, history: bool = True) -> List[str]:
    """Secrets in tracked files, and in every commit's added lines when `history`."""
    findings: List[str] = []
    listed = git(project, "ls-files", "-z")
    for name in filter(None, listed.stdout.split("\0")):
        path = project / name
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            match = SECRET_RE.search(line)
            if match:
                findings.append(f"{name}:{lineno}: {_kind(match)}")
    if history:
        log = git(project, "log", "--all", "-p", "--no-color", "--unified=0",
                  "--format=commit %h")
        commit = "?"
        for line in log.stdout.splitlines():
            if line.startswith("commit "):
                commit = line.split()[1]
            elif line.startswith("+") and not line.startswith("+++"):
                match = SECRET_RE.search(line)
                if match:
                    finding = f"history {commit}: {_kind(match)}"
                    if finding not in findings:
                        findings.append(finding)
    return findings


def _kind(match: re.Match) -> str:
    names = list(SECRET_PATTERNS)
    for key, value in match.groupdict().items():
        if value:
            return names[int(key[1:])]
    return "secret"


def dependency_audits(project: Path) -> List[Dict[str, Any]]:
    """One audit per dependency manifest found. A manifest whose auditor is not installed
    is a finding, not a pass: an unaudited dependency set is the thing the gate guards."""
    results: List[Dict[str, Any]] = []
    skip = slices.SKIP_DIRS
    for req in sorted(project.rglob("requirements*.txt")):
        if skip.intersection(req.relative_to(project).parts):
            continue
        tool = shutil.which("pip-audit")
        rel = str(req.relative_to(project))
        if not tool:
            results.append({"manifest": rel, "ok": False,
                            "detail": "pip-audit is not installed (pip install pip-audit)"})
            continue
        proc = subprocess.run([tool, "-r", str(req), "--progress-spinner", "off"], cwd=project,
                              capture_output=True, text=True, timeout=900)
        results.append({"manifest": rel, "ok": proc.returncode == 0,
                        "detail": _tail(proc.stdout + proc.stderr)})
    for lock in sorted(project.rglob("package-lock.json")):
        if skip.intersection(lock.relative_to(project).parts):
            continue
        tool = shutil.which("npm")
        rel = str(lock.relative_to(project))
        if not tool:
            results.append({"manifest": rel, "ok": False, "detail": "npm is not installed"})
            continue
        proc = subprocess.run([tool, "audit", "--omit=dev", "--audit-level=high"],
                              cwd=lock.parent, capture_output=True, text=True, timeout=900)
        results.append({"manifest": rel, "ok": proc.returncode == 0,
                        "detail": _tail(proc.stdout + proc.stderr)})
    return results


def _tail(text: str, lines: int = 8) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def threat_model_blockers(project: Path) -> List[str]:
    path = project / THREAT_MODEL
    if not path.is_file():
        return [f"{THREAT_MODEL} is missing"]
    text = path.read_text(encoding="utf-8")
    heads = {h.strip().lower() for h in re.findall(r"^#{2,3}\s+(.+?)\s*$", text, re.M)}
    missing = [s for s in THREAT_SECTIONS if s.lower() not in heads]
    reasons = [f"{THREAT_MODEL} has no '## {s}' section" for s in missing]
    if re.search(r"\b(TODO|TBD)\b", text):
        reasons.append(f"{THREAT_MODEL} still has TODO/TBD in it")
    return reasons


# --------------------------------------------------------------------------- phases

def release_blockers(project: Path, st: Dict[str, Any], tag: str) -> List[str]:
    reasons: List[str] = []
    cfg = ship(st)
    if not cfg.get("target"):
        reasons.append("no deploy target recorded (ship.py config --target ...)")
    if not re.fullmatch(r"v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?", tag):
        reasons.append(f"tag {tag!r} is not a semantic version like v1.2.0")
    if commit_of(project, tag):
        reasons.append(f"tag {tag} already exists")
    changes = dirty(project)
    if changes:
        reasons.append(f"working tree is not clean ({len(changes)} change(s)); commit first")
    changelog = project / "CHANGELOG.md"
    if not changelog.is_file() or tag.lstrip("v") not in changelog.read_text(encoding="utf-8"):
        reasons.append(f"CHANGELOG.md has no entry for {tag}")
    staged = latest(st, "staging")
    if not staged or not same_commit(project, staged["version"], head(project)):
        reasons.append("HEAD has not been deployed to staging and smoke-checked "
                       "(ship.py record staging --url ...)")
    return reasons


def devops_blockers(project: Path, st: Dict[str, Any]) -> List[str]:
    reasons = list(state.blockers(st, "devops"))
    cfg = ship(st)
    reasons += ci_blockers(project, st)
    reasons += upkeep_blockers(project)
    release = cfg.get("release")
    if not release:
        reasons.append("no release tagged (ship.py release v1.0.0)")
    else:
        staged = [d for d in deploys(st, "staging") if d["kind"] == "deploy"
                  and same_commit(project, d["version"], release["tag"])]
        if not staged:
            reasons.append(f"release {release['tag']} has no passing staging deploy")
    return reasons


def launch_blockers(project: Path, st: Dict[str, Any]) -> List[str]:
    reasons = list(state.blockers(st, "launch"))
    if not state.gate_passed(st, "test"):
        reasons.append("test gate has not passed (ship.py test)")
    release = ship(st).get("release")
    live = latest(st, "production")
    if not release:
        reasons.append("no release tagged")
    if not live:
        reasons.append("nothing deployed to production (ship.py record production --url ...)")
        return reasons
    if release and not same_commit(project, live["version"], release["tag"]):
        reasons.append(f"production runs {live['version']}, not release {release['tag']}")
    reasons += https_required(live["url"])
    after = deploys(st, "production")[deploys(st, "production").index(live) + 1:]
    rolled = next((d for d in after if d["kind"] == "rollback"
                   and d["version"] != live["version"]), None)
    restored = rolled and next((d for d in after[after.index(rolled) + 1:]
                                if d["kind"] == "restore" and d["version"] == live["version"]),
                               None)
    if not rolled:
        reasons.append("rollback not rehearsed: roll production back to the previous version "
                       "and record it (ship.py record production --kind rollback ...)")
    elif not restored:
        reasons.append(f"rolled back to {rolled['version']} but never restored "
                       f"{live['version']} (ship.py record production --kind restore ...)")
    else:
        now = smoke(restored["url"], ship(st).get("health", "/"))
        if not now["ok"]:
            reasons.append(f"production is not answering now: {now.get('status') or now.get('error')}")
    return reasons


def run_test_gate(project: Path, st: Dict[str, Any]) -> Dict[str, Any]:
    reasons = list(state.blockers(st, "test"))
    cfg = slices.build_config(st)
    command = cfg.get("test_command")
    roots = cfg.get("tests") or list(slices.DEFAULT_TESTS)
    feature = project / FEATURE
    names = list(scenarios(feature.read_text(encoding="utf-8"))) if feature.is_file() else []
    unmapped = slices.unmapped_scenarios(project, names, roots)
    result: Dict[str, Any] = {"exit": None, "tail": ""}
    if not names:
        reasons.append(f"{FEATURE} has no scenarios")
    reasons += [f"scenario not named in any test: '{n}'" for n in unmapped]
    if not command:
        reasons.append("no test command recorded (pk slice config --test-command ...)")
    elif not reasons:
        result = slices.run_tests(project, command)
        if result["exit"] != 0:
            reasons.append(f"test command failed (exit {result['exit']}): {command}")
    lines = [f"# Test report: {st['project']}", "",
             f"- **Result:** {'PASS' if not reasons else 'FAIL'}",
             f"- **Commit:** {head(project) or 'unknown'}",
             f"- **Run at:** {_now()}",
             f"- **Command:** `{command}`",
             f"- **Scenarios mapped:** {len(names) - len(unmapped)} of {len(names)}", ""]
    if reasons:
        lines += ["## What failed", ""] + [f"- {r}" for r in reasons] + [""]
    if result["tail"]:
        lines += ["## Output (last lines)", "", "```", result["tail"], "```", ""]
    return {"passed": not reasons, "reasons": reasons, "report": "\n".join(lines),
            "mapped": len(names) - len(unmapped), "scenarios": len(names)}


def run_audit(project: Path, st: Dict[str, Any]) -> Dict[str, Any]:
    reasons = list(state.blockers(st, "security"))
    secrets = scan_secrets(project)
    audits = dependency_audits(project)
    reasons += [f"secret: {s}" for s in secrets]
    reasons += [f"dependencies {a['manifest']}: {a['detail'].splitlines()[-1] if a['detail'] else 'failed'}"
                for a in audits if not a["ok"]]
    reasons += threat_model_blockers(project)
    lines = [f"# Security audit: {st['project']}", "",
             f"- **Result:** {'PASS' if not reasons else 'FAIL'}",
             f"- **Commit:** {head(project) or 'unknown'}",
             f"- **Run at:** {_now()}", "",
             "## Secrets (tracked files and every commit)", ""]
    lines += [f"- {s}" for s in secrets] or ["- none found"]
    lines += ["", "## Dependencies", ""]
    lines += [f"- `{a['manifest']}`: {'clean' if a['ok'] else 'FINDINGS'}" for a in audits] \
        or ["- no requirements*.txt or package-lock.json found"]
    for a in audits:
        if not a["ok"] and a["detail"]:
            lines += ["", f"```\n{a['detail']}\n```"]
    lines += ["", "## Threat model", "",
              f"- `{THREAT_MODEL}`: " + ("complete" if not threat_model_blockers(project)
                                         else "; ".join(threat_model_blockers(project)))]
    if reasons:
        lines += ["", "## What failed", ""] + [f"- {r}" for r in reasons]
    return {"passed": not reasons, "reasons": reasons, "report": "\n".join(lines) + "\n",
            "secrets": secrets, "audits": audits}


# --------------------------------------------------------------------------- CLI

def _emit(data: Any) -> None:
    print(json.dumps(data, indent=2))


def _refuse(reasons: List[str]) -> int:
    print("REFUSED", file=sys.stderr)
    for reason in reasons:
        print(f"  - {reason}", file=sys.stderr)
    return 1


def _save(st: Dict[str, Any], project: Path) -> None:
    st["resume_point"] = state.describe_next(st)
    state.save(st, project)
    state.registry_upsert(st, project)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="ship.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-C", "--dir", default=".", help="project directory (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("config", help="record the deploy target and health path")
    p.add_argument("--target", choices=TARGETS)
    p.add_argument("--health", help="path that answers 200 when the service is up")
    p.add_argument("--env", action="append", default=[], dest="envs",
                   help="a setting the deployment needs (name only, never the value)")
    p.add_argument("--service", help="the service or app name on the target")
    sub.add_parser("status", help="what is configured, deployed and recorded")
    p = sub.add_parser("smoke", help="is this deployment up?")
    p.add_argument("url")
    p.add_argument("--health")
    p = sub.add_parser("record", help="smoke-check a deployment, then record it")
    p.add_argument("env", choices=ENVS)
    p.add_argument("--url", required=True)
    p.add_argument("--version", help="commit or tag deployed (default: HEAD)")
    p.add_argument("--kind", choices=KINDS, default="deploy")
    p = sub.add_parser("release", help="tag HEAD as a release")
    p.add_argument("tag")
    p = sub.add_parser("done", help="record a phase complete if its checks pass")
    p.add_argument("phase", choices=("devops", "launch"))
    sub.add_parser("test", help="run the test gate")
    sub.add_parser("audit", help="run the security gate")
    args = parser.parse_args(argv)

    project = Path(args.dir)
    try:
        st = state.load(project)
        cfg = ship(st)

        if args.command == "config":
            if args.target:
                cfg["target"] = args.target
            if args.health:
                cfg["health"] = args.health
            if args.service:
                cfg["service"] = args.service
            for name in args.envs:
                if "=" in name:
                    raise ShipError("record setting names only (--env NAME), never values")
                cfg.setdefault("env", [])
                if name not in cfg["env"]:
                    cfg["env"].append(name)
            _save(st, project)
            _emit({k: v for k, v in cfg.items() if k != "deploys"})
            return 0

        if args.command == "status":
            _emit({"config": {k: v for k, v in cfg.items() if k not in ("deploys",)},
                   "head": head(project),
                   "staging": latest(st, "staging"), "production": latest(st, "production"),
                   "gates": {g: st["gates"][g].get("ruling") for g in ("test", "security")},
                   "phases": {p: st["phases"][p]["status"]
                              for p in ("build", "devops", "test", "security", "launch")},
                   "next": state.describe_next(st)})
            return 0

        if args.command == "smoke":
            result = smoke(args.url, args.health or cfg.get("health", "/"))
            _emit(result)
            return 0 if result["ok"] else 1

        if args.command == "record":
            if not cfg.get("target"):
                return _refuse(["no deploy target recorded (ship.py config --target ...)"])
            version = args.version or head(project)
            if not version:
                return _refuse(["no version given and HEAD is unknown"])
            reasons: List[str] = []
            if args.env == "production":
                if not state.gate_passed(st, "security"):
                    reasons.append("security gate has not passed (ship.py audit)")
                if args.kind == "deploy" and not any(
                        same_commit(project, d["version"], version) for d in deploys(st, "staging")):
                    reasons.append(f"{version} was never deployed to staging")
                reasons += https_required(args.url)
            if reasons:
                return _refuse(reasons)
            result = smoke(args.url, cfg.get("health", "/"))
            if not result["ok"]:
                return _refuse([f"smoke check failed for {result['url']}: "
                                f"{result.get('status') or result.get('error')}"])
            entry = {"env": args.env, "kind": args.kind, "url": args.url.rstrip("/"),
                     "version": version, "at": _now(),
                     "smoke": {"status": result["status"], "ms": result["ms"]}}
            cfg.setdefault("deploys", []).append(entry)
            if st["phases"]["devops"]["status"] == "not started":
                st["phases"]["devops"]["status"] = "in progress"
            _save(st, project)
            _emit({"recorded": entry, "next": state.describe_next(st)})
            return 0

        if args.command == "release":
            reasons = release_blockers(project, st, args.tag)
            if reasons:
                return _refuse(reasons)
            out = git(project, "tag", "-a", args.tag, "-m", f"Release {args.tag}")
            if out.returncode != 0:
                return _refuse([f"git tag failed: {out.stderr.strip()}"])
            cfg["release"] = {"tag": args.tag, "commit": head(project), "at": _now()}
            _save(st, project)
            _emit({"release": cfg["release"],
                   "push": f"git push origin {args.tag}"})
            return 0

        if args.command == "done":
            reasons = devops_blockers(project, st) if args.phase == "devops" \
                else launch_blockers(project, st)
            if reasons:
                return _refuse(reasons)
            state.set_phase(st, args.phase, "complete")
            _save(st, project)
            _emit({"phase": args.phase, "status": "complete", "next": state.describe_next(st)})
            return 0

        if args.command in ("test", "audit"):
            phase, gate, report = (("test", "test", TEST_REPORT) if args.command == "test"
                                   else ("security", "security", AUDIT_REPORT))
            ordering = state.blockers(st, phase)
            if ordering:
                return _refuse(ordering)
            result = run_test_gate(project, st) if args.command == "test" \
                else run_audit(project, st)
            path = project / report
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(result["report"], encoding="utf-8")
            state.record_ruling(st, gate, "PASS" if result["passed"] else "FAIL",
                                st["gates"][gate].get("round", 0) + 1, result["reasons"])
            state.set_phase(st, phase, "complete" if result["passed"] else "in progress",
                            [report])
            _save(st, project)
            if not result["passed"]:
                return _refuse(result["reasons"] + [f"report written to {report}"])
            _emit({"gate": gate, "passed": True, "report": report,
                   "next": state.describe_next(st)})
            return 0
    except (state.StateError, slices.SliceError, ShipError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
