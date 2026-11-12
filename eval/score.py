"""Score the filing service against the filing test set (docs/spec.md, "Eval harness").

    python -m eval.score                          # the service in-process, real model
    python -m eval.score --url http://host:8080   # a running service
    python -m eval.score --limit 20               # the first 20 cases (smoke set)

Each case in eval/captures.jsonl is sent to /v1/file as one capture. The ops that come back go
through the Validator exactly as on a device (a rejected batch becomes a note), and are then
compared with the case's expected ops (dumpit_ops.compare). It prints the fully-correct share
per item kind and overall, separately for cases written by the builder and by others, and the
mean cost per capture in euros, and writes eval/report.json with one result per capture id.

The in-process run needs ANTHROPIC_API_KEY; tests pass their own model instead.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, TextIO

from dumpit_ops import Context, decide, differences, fully_correct

HERE = Path(__file__).resolve().parent
CAPTURES = HERE / "captures.jsonl"
REPORT = HERE / "report.json"

KINDS = ("task", "expense", "trip", "edit", "budget", "paste", "note")
CASE_FIELDS = {"id", "today", "tz", "context", "text", "source", "expected_ops", "author"}
OPTIONAL_FIELDS = {"captured_at", "comment"}
CHANGES = ("update", "delete", "complete_task")


def case_kind(case: Dict[str, Any]) -> str:
    """The item kind a case is reported under. A paste is a paste whatever it files; a
    capture that changes an existing item is an edit; otherwise the first thing it creates."""
    if case["source"] == "paste":
        return "paste"
    kinds = [op["op"] for op in case["expected_ops"]]
    if any(k in CHANGES for k in kinds):
        return "edit"
    for op_kind, kind in (("create_trip", "trip"), ("create_expense", "expense"),
                          ("create_task", "task"), ("set_monthly_budget", "budget")):
        if op_kind in kinds:
            return kind
    return "note"


def is_builder(case: Dict[str, Any]) -> bool:
    return case["author"] == "builder"


def load(path: Path = CAPTURES) -> List[Dict[str, Any]]:
    cases = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path.name}:{n}: not JSON ({exc})")
    return cases


TARGET_CASES, TARGET_OTHERS, TARGET_PASTES = 200, 50, 3


def shortfalls(cases: List[Dict[str, Any]]) -> List[str]:
    """What the test set still lacks against docs/backlog.md slice 2; empty when complete."""
    gaps = []
    others = sum(not is_builder(c) for c in cases)
    kinds = {case_kind(c) for c in cases}
    if len(cases) < TARGET_CASES:
        gaps.append(f"{len(cases)} of {TARGET_CASES} captures")
    if others < TARGET_OTHERS:
        gaps.append(f"{others} of {TARGET_OTHERS} captures written by someone other than "
                    "the builder")
    pastes = sum(c["source"] == "paste" for c in cases)
    if pastes < TARGET_PASTES:
        gaps.append(f"{pastes} of {TARGET_PASTES} pasted notes")
    for kind in ("task", "expense", "trip", "edit"):
        if kind not in kinds:
            gaps.append(f"no {kind} captures")
    return gaps


def captured_at(case: Dict[str, Any]) -> str:
    return case.get("captured_at") or f"{case['today']}T09:00:00"


def request_for(case: Dict[str, Any]) -> Dict[str, Any]:
    return {"capture_id": case["id"], "text": case["text"], "source": case["source"],
            "captured_at": captured_at(case), "tz": case["tz"], "currency": "EUR",
            "context": case["context"]}


# A filer sends one request to the service and returns (status code, JSON body).
Filer = Callable[[Dict[str, Any]], "tuple[int, Dict[str, Any]]"]


def in_process_filer(model: Any = None) -> Filer:
    """The service app in this process, with limits that never trip during a run."""
    from fastapi.testclient import TestClient

    from service.app import create_app
    from service.limits import Limits

    client = TestClient(create_app(model=model,
                                   limits=Limits(per_install_daily=10**6, daily_cap_eur=1e9)))
    token = client.post("/v1/install").json()["install_token"]
    headers = {"Authorization": f"Bearer {token}"}

    def file(request: Dict[str, Any]):
        response = client.post("/v1/file", json=request, headers=headers)
        return response.status_code, response.json()
    return file


def url_filer(base: str) -> Filer:
    import httpx

    client = httpx.Client(base_url=base.rstrip("/"), timeout=60.0)
    token = client.post("/v1/install").json()["install_token"]
    headers = {"Authorization": f"Bearer {token}"}

    def file(request: Dict[str, Any]):
        response = client.post("/v1/file", json=request, headers=headers)
        return response.status_code, response.json()
    return file


@dataclass
class Rates:
    """Euros per million tokens; the service's defaults (Claude Haiku 5.5 prices)."""
    eur_per_mtok_in: float = float(os.environ.get("DUMPIT_EUR_PER_MTOK_IN", "0.10"))
    eur_per_mtok_out: float = float(os.environ.get("DUMPIT_EUR_PER_MTOK_OUT", "0.50"))

    def cost(self, usage: Dict[str, int]) -> float:
        return (usage.get("input_tokens", 0) * self.eur_per_mtok_in
                + usage.get("output_tokens", 0) * self.eur_per_mtok_out) / 1_000_000


def score_case(case: Dict[str, Any], file: Filer, rates: Rates) -> Dict[str, Any]:
    status, body = file(request_for(case))
    result: Dict[str, Any] = {"id": case["id"], "kind": case_kind(case),
                              "author": case["author"], "status": status}
    usage = (body.get("usage") or {}) if isinstance(body, dict) else {}
    result["cost_eur"] = round(rates.cost(usage), 6)
    if status != 200:
        result.update(correct=False, error=body.get("error") if isinstance(body, dict)
                      else str(body))
        return result
    filed, verdict = decide(case["text"], body["ops"], source=case["source"],
                            today=date.fromisoformat(case["today"]),
                            context=Context.from_snapshot(case["context"]))
    result["correct"] = fully_correct(filed, case["expected_ops"])
    result["filed_ops"] = filed
    if not verdict.ok:
        result["validator_problems"] = verdict.problems
    if not result["correct"]:
        result["diff"] = differences(filed, case["expected_ops"])
    return result


def _share(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(results)
    correct = sum(r["correct"] for r in results)
    return {"n": n, "correct": correct, "share": round(correct / n, 4) if n else None}


def summarise(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    groups: Dict[str, List[Dict[str, Any]]] = {
        "all": results,
        "builder": [r for r in results if r["author"] == "builder"],
        "others": [r for r in results if r["author"] != "builder"],
    }
    summary: Dict[str, Any] = {}
    for name, group in groups.items():
        by_kind: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in group:
            by_kind[r["kind"]].append(r)
        summary[name] = {"overall": _share(group),
                         "per_kind": {k: _share(by_kind[k]) for k in KINDS if by_kind[k]}}
    costs = [r["cost_eur"] for r in results]
    summary["mean_cost_eur"] = round(sum(costs) / len(costs), 6) if costs else None
    summary["errors"] = sum(r["status"] != 200 for r in results)
    return summary


def _pct(share: Dict[str, Any]) -> str:
    if not share["n"]:
        return "    —"
    return f"{share['share'] * 100:5.1f} %  ({share['correct']}/{share['n']})"


def print_summary(summary: Dict[str, Any], out: TextIO = sys.stdout) -> None:
    for name, title in (("all", "All cases"), ("builder", "Written by the builder"),
                        ("others", "Written by others")):
        group = summary[name]
        out.write(f"\n{title}\n")
        if not group["overall"]["n"]:
            out.write("  (none)\n")
            continue
        for kind, share in group["per_kind"].items():
            out.write(f"  {kind:<8} {_pct(share)}\n")
        out.write(f"  {'overall':<8} {_pct(group['overall'])}\n")
    out.write(f"\nMean cost per capture: €{summary['mean_cost_eur']:.5f}\n")
    if summary["errors"]:
        out.write(f"Service errors: {summary['errors']} (counted as not correct)\n")


def run(cases: Iterable[Dict[str, Any]], file: Filer, *, rates: Optional[Rates] = None,
        model_name: str = "", prompt_version: str = "", report: Optional[Path] = REPORT,
        out: TextIO = sys.stdout, progress: bool = False) -> Dict[str, Any]:
    rates = rates or Rates()
    cases = list(cases)
    results = []
    for n, case in enumerate(cases, 1):
        results.append(score_case(case, file, rates))
        if progress:
            sys.stderr.write(f"\r{n}/{len(cases)}")
    if progress:
        sys.stderr.write("\n")
    summary = summarise(results)
    data = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": model_name, "prompt_version": prompt_version,
            "rates_eur_per_mtok": {"input": rates.eur_per_mtok_in,
                                   "output": rates.eur_per_mtok_out},
            "summary": summary, "results": results}
    print_summary(summary, out)
    if report is not None:
        report.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n",
                          encoding="utf-8")
        out.write(f"Wrote {report}\n")
    return data


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.score", description=__doc__.split("\n")[0])
    parser.add_argument("--captures", type=Path, default=CAPTURES)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--url", help="score a running service instead of one in-process")
    parser.add_argument("--limit", type=int, help="only the first N cases")
    parser.add_argument("--id", action="append", dest="ids", help="only these case ids")
    args = parser.parse_args(argv)

    cases = load(args.captures)
    if args.ids:
        cases = [c for c in cases if c["id"] in set(args.ids)]
    if args.limit:
        cases = cases[:args.limit]

    from service.model import PROMPT_VERSION
    if args.url:
        import httpx
        health = httpx.get(args.url.rstrip("/") + "/v1/health", timeout=30).json()
        file, model_name, prompt = url_filer(args.url), health.get("model", ""), \
            health.get("prompt_version", "")
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.stderr.write("ANTHROPIC_API_KEY is not set (or pass --url)\n")
            return 2
        from service.model import AnthropicModel
        model = AnthropicModel()
        file, model_name, prompt = in_process_filer(model), model.name, PROMPT_VERSION

    for gap in shortfalls(load(args.captures)):
        sys.stderr.write(f"Test set incomplete: {gap}\n")
    started = time.monotonic()
    run(cases, file, model_name=model_name, prompt_version=prompt, report=args.report,
        progress=True)
    print(f"{len(cases)} captures in {time.monotonic() - started:.0f} s "
          f"({model_name}, prompt {prompt})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
