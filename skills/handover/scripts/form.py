#!/usr/bin/env python3
"""The judge form: what a judge evaluates, the exact shape of a verdict, and how three
verdicts combine into one ruling.

Pure functions only, no I/O. Everything here is what a gate depends on, so it is decided by
code a test can pin, never by a model reading the verdicts and summarising them.

    FORM          criteria, verdicts, severities and confidence labels
    validate()    one verdict against the form and the case it claims to judge
    extract()     the JSON object out of a model's reply (fences, prose around it)
    combine()     three valid verdicts -> one ruling
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

FORM_VERSION = 1

# Least to most severe. The order is the combination rule: see combine().
VERDICTS: Tuple[str, ...] = ("SOUND", "FIX FIRST", "NEEDS INFO", "SPLIT", "REJECT")
VERDICT_MEANING: Dict[str, str] = {
    "SOUND": "Buildable as written. Nothing must change before implementation starts.",
    "FIX FIRST": "The direction is right, but specific blocking problems must be fixed "
                 "before implementation. Every one is a finding of severity `blocker` "
                 "with a concrete fix.",
    "NEEDS INFO": "The case is missing something needed to judge it. Every gap is listed "
                  "in `questions`.",
    "SPLIT": "This is more than one product or too large for one plan. Say where to cut "
             "in the findings.",
    "REJECT": "Fundamentally unsound: the core capability cannot work as designed, or the "
              "scope or cost is not credible. Say why in the findings.",
}

# (id, question). The ids are the contract with the validator and the ruling; the
# questions are what the judge is asked. Order is the order they appear everywhere.
CRITERIA: Tuple[Tuple[str, str], ...] = (
    ("job_fit", "Does v1 do the stated job end to end for the named person?"),
    ("scope", "Is the v1 cut the smallest thing that does the job, and does the spec stay "
              "inside it and its out-of-scope list?"),
    ("feasibility", "Can the core capability work as designed? Are the technical risks "
                    "named and credible?"),
    ("failure_modes", "Is the failure-mode table complete, and does every row have an "
                      "acceptance scenario?"),
    ("data_and_rollback", "Is the data model sound, are migrations versioned, and can both "
                          "code and data be rolled back?"),
    ("security_privacy", "Is sensitive data identified and protected, are secrets kept out "
                         "of code and logs?"),
    ("testability", "Are the acceptance criteria executable, and do they cover every v1 "
                    "capability?"),
    ("cost", "Are the effort and running-cost estimates credible, and is the biggest "
             "uncertainty addressed?"),
    ("counter_argument", "Does the design survive its own strongest counter-argument?"),
)
CRITERION_IDS: Tuple[str, ...] = tuple(c for c, _ in CRITERIA)

RATINGS: Tuple[str, ...] = ("pass", "concern", "fail")
SEVERITIES: Tuple[str, ...] = ("blocker", "major", "minor")
# How the judge knows. CITED points at specific text in the case; REASONED follows from
# it; SPECULATING is a plausible risk the case neither confirms nor rules out. Greenfield
# plans have nothing runnable, so SPECULATING is normal there, not a defect.
CONFIDENCES: Tuple[str, ...] = ("CITED", "REASONED", "SPECULATING")

TIERS: Tuple[str, ...] = ("standard", "high")

# Families a verdict may come from. Kept in step with doctor.FAMILY_BY_KEY by a test.
FAMILIES: Tuple[str, ...] = ("openai", "google", "moonshot", "xai", "deepseek", "mistral",
                             "cohere")
EXCLUDED_FAMILY = "anthropic"
SEATS_REQUIRED = 3


class FormError(ValueError):
    """A verdict or a panel does not satisfy the form."""


# --------------------------------------------------------------------------- extract

_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


def extract(reply: str) -> Dict[str, Any]:
    """The verdict object from a model's reply.

    Models wrap JSON in fences or add a sentence before it however firmly they are told not
    to. Accept exactly one object: a fenced block if present, else the outermost braces.
    Anything that still does not parse is the judge's error, reported rather than guessed.
    """
    text = (reply or "").strip()
    if not text:
        raise FormError("the reply is empty")
    candidates: List[str] = [m.group(1) for m in _FENCE.finditer(text)]
    if not candidates:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise FormError("the reply contains no JSON object")
        candidates = [text[start:end + 1]]
    if len(candidates) > 1:
        raise FormError(f"the reply contains {len(candidates)} JSON blocks; expected one")
    try:
        data = json.loads(candidates[0])
    except json.JSONDecodeError as exc:
        raise FormError(f"the reply is not valid JSON: {exc.msg} at line {exc.lineno}")
    if not isinstance(data, dict):
        raise FormError("the reply's JSON is not an object")
    return data


# --------------------------------------------------------------------------- validate

def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate(verdict: Dict[str, Any], case_id: str) -> List[str]:
    """Every way `verdict` fails the form. Empty means it is valid.

    The family is deliberately not read from the verdict: a judge cannot be trusted to say
    who it is. The runner records the seat it actually called.
    """
    problems: List[str] = []
    if verdict.get("form_version") != FORM_VERSION:
        problems.append(f"form_version must be {FORM_VERSION}")
    if verdict.get("case_id") != case_id:
        problems.append("case_id does not match the case this round sent; the verdict is "
                        "for a different version of the plan")
    ruling = verdict.get("verdict")
    if ruling not in VERDICTS:
        problems.append(f"verdict must be one of: {', '.join(VERDICTS)}")
    if not _text(verdict.get("summary")):
        problems.append("summary is empty")

    criteria = verdict.get("criteria")
    ratings: Dict[str, str] = {}
    if not isinstance(criteria, list):
        problems.append("criteria must be a list")
        criteria = []
    for i, item in enumerate(criteria):
        if not isinstance(item, dict):
            problems.append(f"criteria[{i}] is not an object")
            continue
        cid, rating = item.get("id"), item.get("rating")
        if cid not in CRITERION_IDS:
            problems.append(f"criteria[{i}]: unknown id {cid!r}")
            continue
        if cid in ratings:
            problems.append(f"criteria: {cid} appears twice")
        if rating not in RATINGS:
            problems.append(f"criteria {cid}: rating must be one of {', '.join(RATINGS)}")
        elif rating != "pass" and not _text(item.get("note")):
            problems.append(f"criteria {cid}: a {rating} needs a note saying why")
        ratings[cid] = rating
    missing = [c for c in CRITERION_IDS if c not in ratings]
    if missing:
        problems.append("criteria not rated: " + ", ".join(missing))

    findings = verdict.get("findings")
    if not isinstance(findings, list):
        problems.append("findings must be a list")
        findings = []
    blockers = 0
    for i, item in enumerate(findings):
        where = f"findings[{i}]"
        if not isinstance(item, dict):
            problems.append(f"{where} is not an object")
            continue
        if item.get("criterion") not in CRITERION_IDS:
            problems.append(f"{where}: criterion must be one of the criteria ids")
        severity = item.get("severity")
        if severity not in SEVERITIES:
            problems.append(f"{where}: severity must be one of {', '.join(SEVERITIES)}")
        if item.get("confidence") not in CONFIDENCES:
            problems.append(f"{where}: confidence must be one of {', '.join(CONFIDENCES)}")
        for field in ("claim", "evidence"):
            if not _text(item.get(field)):
                problems.append(f"{where}: {field} is empty")
        if severity in ("blocker", "major") and not _text(item.get("fix")):
            problems.append(f"{where}: a {severity} needs a concrete fix")
        if severity == "blocker":
            blockers += 1

    questions = verdict.get("questions", [])
    if not isinstance(questions, list) or not all(_text(q) for q in questions):
        problems.append("questions must be a list of non-empty strings")
        questions = []

    # Consistency: the verdict must be what the findings say it is.
    if ruling == "SOUND":
        if blockers:
            problems.append("SOUND with a blocker finding is contradictory; use FIX FIRST")
        if "fail" in ratings.values():
            problems.append("SOUND with a failed criterion is contradictory")
    if ruling == "FIX FIRST" and not blockers:
        problems.append("FIX FIRST needs at least one blocker finding, each with a fix")
    if ruling == "NEEDS INFO" and not questions:
        problems.append("NEEDS INFO needs at least one question")
    if ruling in ("SPLIT", "REJECT") and not findings:
        problems.append(f"{ruling} needs at least one finding saying why")
    return problems


# --------------------------------------------------------------------------- panel

def check_panel(families: Sequence[str]) -> List[str]:
    """Why these seats are not a valid panel. Empty means they are."""
    problems: List[str] = []
    if EXCLUDED_FAMILY in families:
        problems.append(f"{EXCLUDED_FAMILY} wrote the plan and cannot judge it")
    seen = [f for f in families if f != EXCLUDED_FAMILY]
    dupes = sorted({f for f in seen if seen.count(f) > 1})
    if dupes:
        problems.append("one family holds two seats: " + ", ".join(dupes))
    unknown = sorted({f for f in seen if f not in FAMILIES})
    if unknown:
        problems.append("unknown family: " + ", ".join(unknown))
    if len(set(seen)) != SEATS_REQUIRED:
        problems.append(f"{len(set(seen))} distinct families; the panel needs exactly "
                        f"{SEATS_REQUIRED}")
    return problems


# --------------------------------------------------------------------------- combine

_SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}
_CONFIDENCE_RANK = {c: i for i, c in enumerate(CONFIDENCES)}
_CRITERION_RANK = {c: i for i, c in enumerate(CRITERION_IDS)}


def _rank(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Most important first: severity, then how well-founded, then criterion order."""
    return sorted(findings, key=lambda f: (_SEVERITY_RANK[f["severity"]],
                                           _CONFIDENCE_RANK[f["confidence"]],
                                           _CRITERION_RANK[f["criterion"]], f["id"]))


def combine(seats: Sequence[Dict[str, Any]], tier: str = "standard") -> Dict[str, Any]:
    """Three seat records -> one ruling.

    Each seat is {"family", "model", "transport", "verdict": <a valid verdict>}.

    The rule is the median by severity: the ruling is the most severe verdict that at least
    two of three judges reached or exceeded. One outlier can neither sink a plan (a lone
    REJECT) nor wave it through (a lone SOUND); outliers are reported as dissent.

    At tier `high`, a FIX FIRST whose blockers are all SPECULATING becomes NEEDS INFO: the
    judges suspect problems they cannot point at. Greenfield plans should use `standard`,
    because nothing is runnable yet and every finding is necessarily speculative.
    """
    if tier not in TIERS:
        raise FormError(f"tier must be one of {', '.join(TIERS)}")
    families = [s["family"] for s in seats]
    problems = check_panel(families)
    if problems:
        raise FormError("; ".join(problems))
    case_ids = {s["verdict"]["case_id"] for s in seats}
    if len(case_ids) != 1:
        raise FormError("the verdicts judged different versions of the case")

    ordered = sorted(seats, key=lambda s: VERDICTS.index(s["verdict"]["verdict"]))
    ruling = ordered[1]["verdict"]["verdict"]

    findings: List[Dict[str, Any]] = []
    questions: List[Dict[str, str]] = []
    matrix: Dict[str, Dict[str, str]] = {c: {} for c in CRITERION_IDS}
    for seat in sorted(seats, key=lambda s: s["family"]):
        verdict, family = seat["verdict"], seat["family"]
        for n, item in enumerate(verdict["findings"], start=1):
            findings.append({
                "id": f"{family}-{n}", "family": family,
                "criterion": item["criterion"], "severity": item["severity"],
                "confidence": item["confidence"], "claim": item["claim"].strip(),
                "evidence": item["evidence"].strip(), "fix": (item.get("fix") or "").strip(),
            })
        questions += [{"family": family, "question": q.strip()}
                      for q in verdict.get("questions", [])]
        for item in verdict["criteria"]:
            matrix[item["id"]][family] = item["rating"]

    blockers = _rank([f for f in findings if f["severity"] == "blocker"])
    downgraded = False
    if tier == "high" and ruling == "FIX FIRST" and blockers and \
            all(f["confidence"] == "SPECULATING" for f in blockers):
        ruling, downgraded = "NEEDS INFO", True

    # A SOUND majority passes; a minority's blockers are dissent, not open fixes.
    open_fixes = [] if ruling == "SOUND" else blockers
    dissent = [{"family": s["family"], "verdict": s["verdict"]["verdict"],
                "summary": s["verdict"]["summary"].strip()}
               for s in seats if s["verdict"]["verdict"] != ruling]
    return {
        "form_version": FORM_VERSION,
        "case_id": case_ids.pop(),
        "tier": tier,
        "ruling": ruling,
        "downgraded": downgraded,
        "verdicts": [{"family": s["family"], "model": s.get("model", ""),
                      "transport": s.get("transport", ""),
                      "verdict": s["verdict"]["verdict"],
                      "summary": s["verdict"]["summary"].strip()}
                     for s in sorted(seats, key=lambda s: s["family"])],
        "open_fixes": open_fixes,
        "dissent_blockers": blockers if ruling == "SOUND" else [],
        "recommended": _rank([f for f in findings if f["severity"] == "major"]),
        "minor": _rank([f for f in findings if f["severity"] == "minor"]),
        "questions": questions,
        "dissent": dissent,
        "criteria": matrix,
    }


def fix_label(fix: Dict[str, Any], width: int = 160) -> str:
    """One line per open fix, as recorded in pipeline.json."""
    text = f"{fix['id']}: {fix['claim']}"
    return text if len(text) <= width else text[:width - 1] + "…"


def passes(ruling: Optional[str], open_fixes: Sequence[Any]) -> bool:
    """Mirrors state.gate_passed, so a ruling can be explained before it is recorded."""
    return ruling == "SOUND" or (ruling == "FIX FIRST" and not open_fixes)
