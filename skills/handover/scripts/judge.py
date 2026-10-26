#!/usr/bin/env python3
"""The judge panel for Project Kit: build the case, send it to three model families,
validate each verdict, combine them into a ruling and record it.

    judge.py seats                 which three seats would sit, and how each is reached
    judge.py case                  write judge/round-<n>/case.json and brief.md
    judge.py run                   call the api and cli seats; list the paste seats
    judge.py accept --family F --file reply.txt
                                   validate a reply you pasted by hand
    judge.py status                every seat's verdict for this round, valid or not
    judge.py combine               three valid verdicts -> ruling.json, docs/ruling.md
    judge.py record                re-check the ruling against the verdicts and record it

Every step re-derives what it depends on from files on disk: `combine` re-validates the
raw replies, `record` re-combines them and rebuilds the case from docs/. A hand-edited
ruling, or a plan that changed after it was judged, is refused rather than recorded.

Exit codes: 0 done, 1 refused (reasons on stderr), 2 usage or state error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "pipeline" / "scripts"))
# scripts/doctor.py lives at the plugin root, three levels up from this file.
sys.path.insert(0, str(HERE.parents[2] / "scripts"))

import doctor  # noqa: E402
import form  # noqa: E402
import state  # noqa: E402

CASE_VERSION = 1
# Rounds of judging before /verdict must stop and ask. The judges have no memory, so an
# unbounded REJECT -> revise -> REJECT loop burns credit without converging.
MAX_ROUNDS = 3
# The most a project may raise its limit to (`pk judge rounds <n>`, used by /remediate).
# The budget cap still applies on top; this stops a loop that is not converging.
HARD_MAX_ROUNDS = 10

DOCUMENTS: Tuple[Tuple[str, str], ...] = (
    ("research", "docs/research.md"),
    ("proposal", "docs/proposal.md"),
    ("spec", "docs/spec.md"),
    ("acceptance", "docs/acceptance.feature"),
)
CHANGES = "docs/changes.md"
RULING_MD = "docs/ruling.md"
COUNTER_HEADING = "Strongest counter-argument"

# family -> (wire format, endpoint, default model). Models move faster than this file:
# override one with PROJECT_KIT_MODEL_<FAMILY>=<model> in the panel .env.
API_SPECS: Dict[str, Tuple[str, str, str]] = {
    "openai": ("chat", "https://api.openai.com/v1/chat/completions", "gpt-4o"),
    "moonshot": ("chat", "https://api.moonshot.ai/v1/chat/completions", "kimi-k2.6"),
    "xai": ("chat", "https://api.x.ai/v1/chat/completions", "grok-4"),
    "deepseek": ("chat", "https://api.deepseek.com/chat/completions", "deepseek-chat"),
    "mistral": ("chat", "https://api.mistral.ai/v1/chat/completions", "mistral-large-latest"),
    "google": ("gemini", "https://generativelanguage.googleapis.com/v1beta/models/"
                         "{model}:generateContent", "gemini-pro-latest"),
}
# USD per million tokens (input, output). Estimates for the budget cap, deliberately on
# the high side; override with PROJECT_KIT_PRICE_<FAMILY>=<in>,<out>.
PRICES: Dict[str, Tuple[float, float]] = {
    "openai": (2.5, 10.0), "google": (1.25, 10.0), "moonshot": (0.6, 2.5),
    "xai": (3.0, 15.0), "deepseek": (0.3, 1.2), "mistral": (2.0, 6.0),
}
EXPECTED_OUTPUT_TOKENS = 4000
CLI_COMMANDS: Dict[str, List[str]] = {"openai": ["codex", "exec"]}

SYSTEM = ("You are an independent reviewer on a three-member panel judging a software plan "
          "you did not write. Follow the brief exactly and reply with one JSON object only.")


class JudgeError(RuntimeError):
    """A precondition for this step was not met."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- rounds

def judge_rounds(st: Dict[str, Any]) -> List[int]:
    return [r["round"] for r in st.get("rounds", []) if r.get("gate") == "judge"]


def current_round(st: Dict[str, Any]) -> int:
    """The round being judged: one past the last recorded ruling."""
    return max(judge_rounds(st), default=0) + 1


def max_rounds(st: Dict[str, Any]) -> int:
    """This project's round limit: MAX_ROUNDS unless the user raised it."""
    return int(st.get("judge_max_rounds", MAX_ROUNDS))


def round_dir(project: Path, round_no: int) -> Path:
    return project / "judge" / f"round-{round_no}"


# --------------------------------------------------------------------------- case

def section(markdown: str, heading: str) -> str:
    """The body of `## heading`, up to the next `## ` heading."""
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", markdown,
                      re.M | re.S)
    return match.group(1).strip() if match else ""


def case_id_of(body: Dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def build_case(project: Path, st: Dict[str, Any], round_no: int) -> Dict[str, Any]:
    """Everything the judges see, as data. The case_id is a hash of it, so a verdict is
    bound to the exact text it judged."""
    problems: List[str] = []
    documents: Dict[str, str] = {}
    for name, rel in DOCUMENTS:
        path = project / rel
        if not path.is_file() or not path.read_text().strip():
            problems.append(f"{rel} is missing or empty")
        else:
            documents[name] = path.read_text()

    counter = section(documents.get("spec", ""), COUNTER_HEADING)
    if "spec" in documents and (len(counter) < 40 or counter.startswith("<")):
        problems.append(f"docs/spec.md has no real '## {COUNTER_HEADING}' section; the judges "
                        "are given it to test, so /design must write it")

    previous = None
    if round_no > 1:
        prior = round_dir(project, round_no - 1) / "ruling.json"
        if not prior.is_file():
            problems.append(f"round {round_no - 1} has no ruling.json to carry forward")
        else:
            ruling = json.loads(prior.read_text())
            changes_path = project / CHANGES
            changes = changes_path.read_text() if changes_path.is_file() else ""
            ids = [f["id"] for f in ruling["open_fixes"]]
            if not changes.strip():
                problems.append(f"{CHANGES} is missing: round {round_no} must say what changed "
                                "since the last ruling, fix by fix")
            else:
                unanswered = [i for i in ids if i not in changes]
                if unanswered:
                    problems.append(f"{CHANGES} does not answer open fix(es): "
                                    + ", ".join(unanswered))
            previous = {
                "round": round_no - 1,
                "ruling": ruling["ruling"],
                "open_fixes": [{"id": f["id"], "claim": f["claim"], "fix": f["fix"]}
                               for f in ruling["open_fixes"]],
                "questions": ruling.get("questions", []),
                "changes": changes,
            }
    if problems:
        raise JudgeError("; ".join(problems))

    body = {
        "case_version": CASE_VERSION,
        "form_version": form.FORM_VERSION,
        "project": st["project"],
        "round": round_no,
        "documents": documents,
        "counter_argument": counter,
        "previous": previous,
    }
    return {**body, "case_id": case_id_of(body)}


def render_brief(case: Dict[str, Any]) -> str:
    """The whole prompt each judge receives. Generated from the form, so the brief and the
    validator cannot drift apart."""
    out: List[str] = [
        f"# Independent review: {case['project']} (round {case['round']})",
        "",
        "You are one of three independent reviewers, each from a different AI company. The "
        "plan below was written by Claude (Anthropic). Your job is to find what is wrong "
        "with it before anyone builds it. Be rigorous, not polite: a weak plan that passes "
        "costs far more than a strong plan that is questioned.",
        "",
        "## Rules",
        "",
        "1. Judge only what is in this case. Every finding cites the document and section "
        "it rests on, in `evidence`.",
        "2. Rate every criterion below, exactly once.",
        "3. This is a plan, not running software. Label each finding's confidence honestly; "
        "SPECULATING is acceptable when the plan neither confirms nor rules a risk out.",
        "4. Every `blocker` and `major` finding carries a concrete `fix`: what to change, "
        "not just what is wrong.",
        "5. Your verdict must agree with your findings: SOUND has no blockers and no failed "
        "criterion; FIX FIRST has at least one blocker; NEEDS INFO has at least one question.",
        "6. Reply with exactly one JSON object in the format at the end, and nothing else.",
    ]
    if case.get("previous"):
        out += [
            "7. You have no memory of earlier rounds. The previous ruling's open fixes and "
            "the author's changes are included below. Do not re-raise a settled finding "
            "unless the change fails to fix it, and then say specifically why.",
        ]
    out += ["", "## Verdicts", "", "| Verdict | Meaning |", "|---|---|"]
    out += [f"| `{v}` | {form.VERDICT_MEANING[v]} |" for v in form.VERDICTS]
    out += ["", "## Criteria", "", "| id | Question |", "|---|---|"]
    out += [f"| `{cid}` | {question} |" for cid, question in form.CRITERIA]
    out += [
        "",
        "Rate each `pass`, `concern` or `fail`. A `concern` or `fail` needs a `note`.",
        "",
        "## Findings",
        "",
        "| Field | Values |",
        "|---|---|",
        "| `criterion` | one of the criteria ids |",
        "| `severity` | `blocker` (must change before building), `major` (should change), "
        "`minor` (worth noting) |",
        "| `confidence` | `CITED` (points at specific text), `REASONED` (follows from the "
        "text), `SPECULATING` (plausible, neither confirmed nor ruled out) |",
        "| `claim` | what is wrong, in one or two sentences |",
        "| `evidence` | the document and section, quoted where it helps |",
        "| `fix` | the concrete change; required for blocker and major |",
        "",
        "## Reply format",
        "",
        "```json",
        json.dumps({
            "form_version": form.FORM_VERSION,
            "case_id": case["case_id"],
            "verdict": " | ".join(form.VERDICTS),
            "summary": "two or three sentences: the verdict and the main reason",
            "criteria": [{"id": cid, "rating": "pass | concern | fail", "note": ""}
                         for cid in form.CRITERION_IDS],
            "findings": [{"criterion": "scope", "severity": "blocker | major | minor",
                          "confidence": "CITED | REASONED | SPECULATING",
                          "claim": "", "evidence": "", "fix": ""}],
            "questions": [],
        }, indent=2, ensure_ascii=False),
        "```",
        "",
        f"Copy `case_id` exactly: `{case['case_id']}`. It binds your verdict to this "
        "version of the plan.",
    ]
    previous = case.get("previous")
    if previous:
        out += ["", f"## Previous round ({previous['round']}): {previous['ruling']}", "",
                "Open fixes the author was asked to make:", ""]
        out += [f"- **{f['id']}**: {f['claim']} Fix asked for: {f['fix']}"
                for f in previous["open_fixes"]] or ["- none"]
        if previous.get("questions"):
            out += ["", "Questions asked:", ""]
            out += [f"- ({q['family']}) {q['question']}" for q in previous["questions"]]
        out += ["", "The author's account of what changed:", "",
                "===== BEGIN docs/changes.md =====", previous["changes"].strip(),
                "===== END docs/changes.md ====="]
    out += ["", "## The author's strongest counter-argument", "",
            "The author was required to argue against their own design. Engage with it under "
            "`counter_argument`: does the design survive it?", "",
            case["counter_argument"], "", "## The case", ""]
    for name, rel in DOCUMENTS:
        out += [f"===== BEGIN {rel} =====", case["documents"][name].strip(),
                f"===== END {rel} =====", ""]
    return "\n".join(out).rstrip() + "\n"


def write_case(project: Path, st: Dict[str, Any]) -> Dict[str, Any]:
    round_no = current_round(st)
    case = build_case(project, st, round_no)
    rdir = round_dir(project, round_no)
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "case.json").write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n")
    (rdir / "brief.md").write_text(render_brief(case))
    return case


def load_case(project: Path, round_no: int) -> Dict[str, Any]:
    path = round_dir(project, round_no) / "case.json"
    if not path.is_file():
        raise JudgeError(f"no case for round {round_no}; run `pk judge case` first")
    return json.loads(path.read_text())


# --------------------------------------------------------------------------- seats

def keys_for(family: str) -> List[str]:
    return [k for k, f in doctor.FAMILY_BY_KEY.items() if f == family]


def model_for(family: str, env: Dict[str, str]) -> str:
    override = env.get(f"PROJECT_KIT_MODEL_{family.upper()}")
    if override:
        return override
    if family in API_SPECS:
        return API_SPECS[family][2]
    return ""


def resolve_seats(env: Dict[str, str], codex_ok: bool, paste: Sequence[str] = (),
                  only: Sequence[str] = ()) -> Tuple[List[Dict[str, str]], List[str]]:
    """Which seats sit and how each is reached. Order of preference per family: a
    `--paste` you asked for, an API key, the codex CLI (openai), a paste seat from the .env.
    Without `only`, the first three reachable families in form.FAMILIES order sit."""
    problems: List[str] = []
    paste_env = set(doctor.paste_families(env))
    asked_paste = {p.lower() for p in paste}

    def transport(family: str) -> Optional[str]:
        if family in asked_paste:
            return "paste"
        has_key = any(env.get(k) for k in keys_for(family))
        if has_key and family in API_SPECS:
            return "api_key"
        if family in CLI_COMMANDS and codex_ok:
            return "cli"
        if family in paste_env or has_key:
            return "paste"           # a key we have no client for still allows pasting
        return None

    wanted = [f.lower() for f in only] or list(form.FAMILIES)
    seats: List[Dict[str, str]] = []
    for family in wanted:
        if family == form.EXCLUDED_FAMILY:
            problems.append(f"{family} wrote the plan and cannot judge it")
            continue
        if family not in form.FAMILIES:
            problems.append(f"unknown family {family!r}")
            continue
        how = transport(family)
        if how is None:
            if only:
                problems.append(f"no way to reach {family}: no key, no CLI, not a paste seat")
            continue
        seats.append({"family": family, "transport": how,
                      "model": model_for(family, env) if how != "paste" else ""})
    if not only:
        seats = seats[:form.SEATS_REQUIRED]
    if not problems:
        problems += form.check_panel([s["family"] for s in seats])
    return seats, problems


def price(family: str, env: Dict[str, str]) -> Tuple[float, float]:
    override = env.get(f"PROJECT_KIT_PRICE_{family.upper()}", "")
    try:
        cin, cout = (float(x) for x in override.split(","))
        return cin, cout
    except ValueError:
        return PRICES.get(family, (5.0, 15.0))


def cost(family: str, tokens_in: int, tokens_out: int, env: Dict[str, str]) -> float:
    cin, cout = price(family, env)
    return round((tokens_in * cin + tokens_out * cout) / 1_000_000, 4)


def estimate(seats: Sequence[Dict[str, str]], brief: str, env: Dict[str, str]) -> float:
    tokens_in = len(brief) // 4
    return round(sum(cost(s["family"], tokens_in, EXPECTED_OUTPUT_TOKENS, env)
                     for s in seats if s["transport"] == "api_key"), 4)


# --------------------------------------------------------------------------- transports

class TransportError(RuntimeError):
    """A seat could not produce a reply."""


def _post(url: str, headers: Dict[str, str], body: Dict[str, Any],
          timeout: float) -> Dict[str, Any]:
    """POST JSON, retrying what is transient. doctor.classify tells a 503 from an
    overloaded model apart from a 429 that means the account has no credit."""
    data = json.dumps(body).encode("utf-8")
    reason = "not attempted"
    for attempt in range(3):
        request = urllib.request.Request(url, data=data, method="POST",
                                         headers={"Content-Type": "application/json",
                                                  **headers})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace")
            verdict, reason = doctor.classify(str(exc.code), text)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            verdict, reason = "transient", f"network: {exc}"
        if verdict != "transient":
            break
        if attempt < 2:
            time.sleep(4 * (attempt + 1))
    raise TransportError(reason)


def call_api(seat: Dict[str, str], brief: str, env: Dict[str, str],
             timeout: float = 600) -> Tuple[str, int, int]:
    """(reply text, input tokens, output tokens) from one API seat."""
    family, model = seat["family"], seat["model"]
    wire, url, _ = API_SPECS[family]
    key = next((env[k] for k in keys_for(family) if env.get(k)), "")
    if not key:
        raise TransportError(f"no API key for {family}")
    if wire == "gemini":
        data = _post(url.format(model=model), {"x-goog-api-key": key},
                     {"systemInstruction": {"parts": [{"text": SYSTEM}]},
                      "contents": [{"role": "user", "parts": [{"text": brief}]}]}, timeout)
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError):
            raise TransportError("no candidate in the response (blocked or empty)")
        usage = data.get("usageMetadata", {})
        return ("".join(p.get("text", "") for p in parts),
                int(usage.get("promptTokenCount", 0)),
                int(usage.get("candidatesTokenCount", 0)))
    data = _post(url, {"Authorization": f"Bearer {key}"},
                 {"model": model, "messages": [{"role": "system", "content": SYSTEM},
                                               {"role": "user", "content": brief}]}, timeout)
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise TransportError("no message in the response")
    usage = data.get("usage", {})
    return text, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))


def call_cli(seat: Dict[str, str], brief: str, env: Dict[str, str],
             timeout: float = 1200) -> Tuple[str, int, int]:
    """A subscription-backed CLI. No tokens are billed to the API, so spend is zero.
    Override the command with PROJECT_KIT_CLI_<FAMILY>, e.g. "codex exec"."""
    family = seat["family"]
    override = env.get(f"PROJECT_KIT_CLI_{family.upper()}") or \
        os.environ.get(f"PROJECT_KIT_CLI_{family.upper()}")
    command = shlex.split(override) if override else list(CLI_COMMANDS[family])
    if not shutil.which(command[0]):
        raise TransportError(f"{command[0]} is not on PATH")
    try:
        done = subprocess.run(command + [SYSTEM + "\n\n" + brief], capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise TransportError(f"{command[0]} failed: {exc}")
    if done.returncode != 0:
        raise TransportError(f"{command[0]} exited {done.returncode}: "
                             f"{(done.stderr or '').strip()[-300:]}")
    return done.stdout, 0, 0


# Indirection so tests can seat recorded fixtures instead of live models.
TRANSPORTS: Dict[str, Callable[..., Tuple[str, int, int]]] = {
    "api_key": call_api, "cli": call_cli}


# --------------------------------------------------------------------------- verdicts

def parse_reply(raw: str, case_id: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    try:
        verdict = form.extract(raw)
    except form.FormError as exc:
        return None, [str(exc)]
    problems = form.validate(verdict, case_id)
    return (verdict if not problems else None), problems


def store_reply(rdir: Path, case_id: str, seat: Dict[str, str], raw: str,
                usd: float = 0.0, tokens: Tuple[int, int] = (0, 0)) -> Dict[str, Any]:
    """Keep the raw reply and an envelope saying who sent it. The family comes from the
    seat that was called, never from the reply."""
    family = seat["family"]
    (rdir / "raw").mkdir(parents=True, exist_ok=True)
    (rdir / "verdicts").mkdir(parents=True, exist_ok=True)
    (rdir / "raw" / f"{family}.txt").write_text(raw)
    verdict, problems = parse_reply(raw, case_id)
    envelope = {"family": family, "model": seat.get("model", ""),
                "transport": seat["transport"], "received_at": _now(), "usd": usd,
                "tokens": {"in": tokens[0], "out": tokens[1]},
                "valid": not problems, "problems": problems, "verdict": verdict}
    (rdir / "verdicts" / f"{family}.json").write_text(
        json.dumps(envelope, indent=2, ensure_ascii=False) + "\n")
    return envelope


def seat_records(rdir: Path, case_id: str) -> List[Dict[str, Any]]:
    """Every seat that replied this round, re-validated from its raw reply against the
    current case. The stored envelope's `valid` is not trusted; the raw text is."""
    records = []
    for path in sorted((rdir / "verdicts").glob("*.json")):
        envelope = json.loads(path.read_text())
        family = envelope["family"]
        raw_path = rdir / "raw" / f"{family}.txt"
        raw = raw_path.read_text() if raw_path.is_file() else ""
        verdict, problems = parse_reply(raw, case_id)
        if path.stem != family:
            problems = problems + [f"{path.name} claims to be {family}"]
        records.append({"family": family, "model": envelope.get("model", ""),
                        "transport": envelope.get("transport", ""),
                        "usd": envelope.get("usd", 0.0),
                        "valid": not problems, "problems": problems, "verdict": verdict})
    return records


def valid_panel(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    valid = [r for r in records if r["valid"]]
    if len(valid) != form.SEATS_REQUIRED:
        detail = ", ".join(f"{r['family']}: {'valid' if r['valid'] else 'invalid'}"
                           for r in records) or "no replies yet"
        raise JudgeError(f"{len(valid)} valid verdict(s); exactly {form.SEATS_REQUIRED} are "
                         f"needed ({detail})")
    problems = form.check_panel([r["family"] for r in valid])
    if problems:
        raise JudgeError("; ".join(problems))
    return valid


# --------------------------------------------------------------------------- ruling

_RATING_MARK = {"pass": "✔ pass", "concern": "! concern", "fail": "✖ fail"}


def _cell(text: str) -> str:
    """Judge-written text inside a markdown table cell: one line, no column breaks."""
    return " ".join((text or "").split()).replace("|", "\\|")


def render_ruling(ruling: Dict[str, Any], project: str, round_no: int,
                  notes: Dict[str, Dict[str, str]]) -> str:
    """docs/ruling.md: the whole ruling in one readable page, generated from ruling.json."""
    passed = form.passes(ruling["ruling"], ruling["open_fixes"])
    gate = "passes" if passed else (
        f"blocked — {len(ruling['open_fixes'])} fix(es) open" if ruling["open_fixes"]
        else "blocked")
    families = [v["family"] for v in ruling["verdicts"]]
    out: List[str] = [
        f"# Judge ruling: {project}, round {round_no}",
        "",
        "> Generated by `pk judge combine` from the three verdicts in "
        f"`judge/round-{round_no}/`. Do not edit: `pk judge record` re-derives it and "
        "refuses a mismatch.",
        "",
        f"**Ruling: {ruling['ruling']}** · judge gate {gate} · case `{ruling['case_id']}` · "
        f"tier `{ruling['tier']}`",
        "",
        "## The panel",
        "",
        "| Judge | Model | How | Verdict | Summary |",
        "|---|---|---|---|---|",
    ]
    out += [f"| {v['family']} | {_cell(v['model']) or '—'} | {v['transport']} | "
            f"**{v['verdict']}** | {_cell(v['summary'])} |" for v in ruling["verdicts"]]
    out += ["", "## What each judge evaluated", "",
            "| Criterion | " + " | ".join(families) + " |",
            "|---|" + "---|" * len(families)]
    for cid, question in form.CRITERIA:
        row = ruling["criteria"].get(cid, {})
        out.append(f"| **{cid}** — {question} | "
                   + " | ".join(_RATING_MARK.get(row.get(f, ""), "—") for f in families)
                   + " |")
    noted = [(cid, f, notes[cid][f]) for cid in form.CRITERION_IDS for f in families
             if notes.get(cid, {}).get(f)]
    if noted:
        out += ["", "Notes on concerns and failures:", ""]
        out += [f"- **{cid}** ({f}): {note}" for cid, f, note in noted]

    def finding_lines(items: List[Dict[str, Any]], numbered: bool) -> List[str]:
        lines: List[str] = []
        for n, f in enumerate(items, start=1):
            lead = f"{n}." if numbered else "-"
            lines += [f"{lead} **{f['id']}** · {f['criterion']} · {f['confidence']} — "
                      f"{f['claim']}",
                      f"   - Evidence: {f['evidence']}"]
            if f.get("fix"):
                lines.append(f"   - Fix: {f['fix']}")
        return lines

    out += ["", "## Open fixes", ""]
    if ruling["open_fixes"]:
        out += ["Blocking. Each must be fixed, and the plan re-judged, before the gate opens. "
                "Most important first.", ""]
        out += finding_lines(ruling["open_fixes"], numbered=True)
    else:
        out.append("None.")
    if ruling.get("dissent_blockers"):
        out += ["", "## Blockers raised by the minority", "",
                "The majority ruled SOUND, so these do not hold the gate. Read them anyway.", ""]
        out += finding_lines(ruling["dissent_blockers"], numbered=False)
    if ruling["dissent"]:
        out += ["", "## Dissent", ""]
        out += [f"- **{d['family']}** said {d['verdict']}: {d['summary']}"
                for d in ruling["dissent"]]
    out += ["", "## Recommended (major, not blocking)", ""]
    out += finding_lines(ruling["recommended"], numbered=False) or ["None."]
    out += ["", "## Minor", ""]
    out += finding_lines(ruling["minor"], numbered=False) or ["None."]
    out += ["", "## Questions", ""]
    out += [f"- ({q['family']}) {q['question']}" for q in ruling["questions"]] or ["None."]
    out += ["", "## How this ruling was reached", "",
            "The ruling is the median verdict by severity (SOUND < FIX FIRST < NEEDS INFO < "
            "SPLIT < REJECT): the most severe verdict at least two of the three judges "
            "reached. One judge alone can neither sink the plan nor pass it."]
    if ruling["downgraded"]:
        out += ["", "At tier `high`, every blocker was SPECULATING, so FIX FIRST became "
                    "NEEDS INFO: the judges suspect problems they could not point at."]
    return "\n".join(out).rstrip() + "\n"


def criteria_notes(records: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    notes: Dict[str, Dict[str, str]] = {c: {} for c in form.CRITERION_IDS}
    for r in records:
        for item in r["verdict"]["criteria"]:
            if item.get("note") and item["rating"] != "pass":
                notes[item["id"]][r["family"]] = item["note"].strip()
    return notes


# --------------------------------------------------------------------------- CLI

def _refuse(reasons: Sequence[str]) -> int:
    print("REFUSED", file=sys.stderr)
    for reason in reasons:
        print(f"  - {reason}", file=sys.stderr)
    return 1


def _emit(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="judge.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-C", "--dir", default=".", help="project directory (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    def seat_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--seat", action="append", default=[],
                       help="seat exactly these families (repeat three times)")
        p.add_argument("--paste", action="append", default=[],
                       help="reach this family by pasting, even if a key exists")

    seat_args(sub.add_parser("seats", help="show which seats would sit"))
    p = sub.add_parser("case", help="write this round's case.json and brief.md")
    p.add_argument("--allow-extra-round", action="store_true",
                   help=f"judge beyond round {MAX_ROUNDS}; only when the user has said so")
    p = sub.add_parser("run", help="call the api and cli seats; list the paste seats")
    seat_args(p)
    p.add_argument("--again", action="store_true",
                   help="call seats that already returned a valid verdict this round")
    p = sub.add_parser("accept", help="validate and store a reply you pasted by hand")
    p.add_argument("--family", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--model", default="", help="the model you pasted into, for the record")
    sub.add_parser("status", help="each seat's verdict this round")
    p = sub.add_parser("rounds", help="show or set this project's round limit")
    p.add_argument("value", nargs="?", type=int,
                   help=f"new limit, 1..{HARD_MAX_ROUNDS}; only when the user has said so")
    p = sub.add_parser("combine", help="three valid verdicts -> ruling")
    p.add_argument("--tier", default="standard", choices=form.TIERS)
    p = sub.add_parser("record", help="verify the ruling and record it in pipeline.json")
    p.add_argument("--allow-extra-round", action="store_true",
                   help=f"record beyond round {MAX_ROUNDS}; only when the user has said so")

    args = parser.parse_args(argv)
    project = Path(args.dir)
    try:
        st = state.load(project)
        round_no = current_round(st)
        rdir = round_dir(project, round_no)
        env = doctor.load_panel_env()

        if args.command == "seats":
            seats, problems = resolve_seats(env, doctor.codex_logged_in(), args.paste,
                                            args.seat)
            if problems:
                seated = ", ".join(s["family"] for s in seats) or "none"
                return _refuse(problems + [f"seated: {seated}"])
            payload: Dict[str, Any] = {"round": round_no, "seats": seats}
            brief = rdir / "brief.md"
            if brief.is_file():
                payload["estimate_usd"] = estimate(seats, brief.read_text(), env)
                payload["budget"] = st["budget"]
            _emit(payload)
            return 0

        if args.command == "rounds":
            if args.value is not None:
                if not 1 <= args.value <= HARD_MAX_ROUNDS:
                    return _refuse([f"the round limit must be 1..{HARD_MAX_ROUNDS}"])
                st["judge_max_rounds"] = args.value
                state.save(st, project)
            _emit({"max_rounds": max_rounds(st), "judged": len(judge_rounds(st)),
                   "rounds_left": max(max_rounds(st) - len(judge_rounds(st)), 0)})
            return 0

        if args.command == "case":
            if round_no > max_rounds(st) and not args.allow_extra_round:
                return _refuse([f"{max_rounds(st)} rounds have been judged; ask the user, then "
                                "pass --allow-extra-round"])
            case = write_case(project, st)
            stale = [r["family"] for r in seat_records(rdir, case["case_id"])
                     if not r["valid"]] if (rdir / "verdicts").is_dir() else []
            _emit({"round": round_no, "case_id": case["case_id"],
                   "case": str(rdir / "case.json"), "brief": str(rdir / "brief.md"),
                   "brief_chars": len((rdir / "brief.md").read_text()),
                   "stale_verdicts": stale})
            return 0

        case = load_case(project, round_no)
        case_id = case["case_id"]

        if args.command == "run":
            seats, problems = resolve_seats(env, doctor.codex_logged_in(), args.paste,
                                            args.seat)
            if problems:
                return _refuse(problems)
            brief = (rdir / "brief.md").read_text()
            done = {r["family"] for r in seat_records(rdir, case_id) if r["valid"]} \
                if (rdir / "verdicts").is_dir() else set()
            todo = [s for s in seats if args.again or s["family"] not in done]
            projected = estimate([s for s in todo if s["transport"] == "api_key"], brief, env)
            budget = st["budget"]
            if budget["spent_usd"] + projected > budget["max_usd"]:
                return _refuse([f"this round is estimated at ${projected}; with ${budget['spent_usd']} "
                                f"already spent that passes the ${budget['max_usd']} cap. "
                                "Raise it with `pk state budget --max <usd>` if the user agrees"])
            results = []
            for seat in todo:
                if seat["transport"] == "paste":
                    results.append({"family": seat["family"], "status": "paste",
                                    "do": f"paste {rdir / 'brief.md'} into {seat['family']}, "
                                          "save the reply, then: pk judge accept --family "
                                          f"{seat['family']} --file <reply file>"})
                    continue
                try:
                    raw, tin, tout = TRANSPORTS[seat["transport"]](seat, brief, env)
                except TransportError as exc:
                    results.append({"family": seat["family"], "status": "failed",
                                    "reason": str(exc)})
                    continue
                usd = cost(seat["family"], tin, tout, env) if seat["transport"] == "api_key" \
                    else 0.0
                envelope = store_reply(rdir, case_id, seat, raw, usd, (tin, tout))
                if usd:
                    st = state.load(project)
                    state.add_spend(st, usd)
                    state.save(st, project)
                results.append({"family": seat["family"],
                                "status": "valid" if envelope["valid"] else "invalid",
                                "usd": usd, "problems": envelope["problems"]})
            skipped = sorted(done & {s["family"] for s in seats}) if not args.again else []
            _emit({"round": round_no, "case_id": case_id, "results": results,
                   "already_valid": skipped,
                   "spent_usd": state.load(project)["budget"]["spent_usd"]})
            return 0 if all(r["status"] in ("valid", "paste") for r in results) else 1

        if args.command == "accept":
            family = args.family.lower()
            if family == form.EXCLUDED_FAMILY:
                return _refuse([f"{family} wrote the plan and cannot judge it"])
            if family not in form.FAMILIES:
                return _refuse([f"unknown family {family!r}; one of "
                                + ", ".join(form.FAMILIES)])
            raw = Path(args.file).read_text()
            envelope = store_reply(rdir, case_id, {"family": family, "transport": "paste",
                                                   "model": args.model}, raw)
            if not envelope["valid"]:
                return _refuse([f"{family}'s reply does not satisfy the form:"]
                               + envelope["problems"]
                               + ["ask the judge to correct exactly these, then accept again"])
            _emit({"round": round_no, "family": family, "status": "valid",
                   "verdict": envelope["verdict"]["verdict"]})
            return 0

        if args.command == "status":
            records = seat_records(rdir, case_id) if (rdir / "verdicts").is_dir() else []
            _emit({"round": round_no, "case_id": case_id,
                   "seats": [{"family": r["family"], "transport": r["transport"],
                              "valid": r["valid"],
                              "verdict": r["verdict"]["verdict"] if r["verdict"] else None,
                              "problems": r["problems"]} for r in records],
                   "ready_to_combine": sum(r["valid"] for r in records)
                   == form.SEATS_REQUIRED})
            return 0

        if args.command == "combine":
            records = valid_panel(seat_records(rdir, case_id))
            ruling = form.combine(records, args.tier)
            ruling["round"] = round_no
            ruling["criteria_notes"] = criteria_notes(records)
            ruling["spend_usd"] = round(sum(r["usd"] for r in records), 4)
            (rdir / "ruling.json").write_text(
                json.dumps(ruling, indent=2, ensure_ascii=False) + "\n")
            page = render_ruling(ruling, st["project"], round_no, ruling["criteria_notes"])
            (rdir / "ruling.md").write_text(page)
            (project / RULING_MD).parent.mkdir(parents=True, exist_ok=True)
            (project / RULING_MD).write_text(page)
            _emit({"round": round_no, "ruling": ruling["ruling"],
                   "gate_would_pass": form.passes(ruling["ruling"], ruling["open_fixes"]),
                   "open_fixes": [form.fix_label(f) for f in ruling["open_fixes"]],
                   "written": [str(rdir / "ruling.json"), str(project / RULING_MD)]})
            return 0

        if args.command == "record":
            if round_no > max_rounds(st) and not args.allow_extra_round:
                return _refuse([f"round {round_no} is past the limit of {max_rounds(st)}; ask the "
                                "user, then pass --allow-extra-round"])
            path = rdir / "ruling.json"
            if not path.is_file():
                return _refuse([f"no ruling for round {round_no}; run `pk judge combine`"])
            recorded = json.loads(path.read_text())
            fresh = form.combine(valid_panel(seat_records(rdir, case_id)), recorded["tier"])
            mismatch = [k for k in ("ruling", "case_id")
                        if fresh[k] != recorded.get(k)]
            if [f["id"] for f in fresh["open_fixes"]] != \
                    [f["id"] for f in recorded.get("open_fixes", [])]:
                mismatch.append("open_fixes")
            if mismatch:
                return _refuse([f"ruling.json disagrees with the verdicts on: "
                                f"{', '.join(mismatch)}; re-run `pk judge combine`"])
            rebuilt = build_case(project, st, round_no)
            if rebuilt["case_id"] != case_id:
                return _refuse(["the plan in docs/ changed after this round was judged; the "
                                "ruling is for a version that no longer exists. Run "
                                "`pk judge case` and judge it again"])
            state.record_ruling(st, "judge", fresh["ruling"], round_no,
                                [form.fix_label(f) for f in fresh["open_fixes"]])
            state.save(st, project)
            state.registry_upsert(st, project)
            _emit({"round": round_no, "ruling": fresh["ruling"],
                   "passed": state.gate_passed(st, "judge"),
                   "open_fixes": st["gates"]["judge"]["open_fixes"],
                   "rounds_left": max(max_rounds(st) - round_no, 0),
                   "next": state.describe_next(st)})
            return 0
    except (JudgeError, form.FormError) as exc:
        return _refuse([str(exc)])
    except state.StateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
