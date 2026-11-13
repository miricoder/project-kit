# Phases

Order is pipeline order. `next` returns the first phase that is not `complete`.

| # | Phase | Skill | Reads | Writes | Gate before it |
|---|---|---|---|---|---|
| 1 | ideate | `/ideate` | the user's idea | `docs/research.md` | — |
| 2 | proposal | `/proposal` | `research.md` | `docs/proposal.md` | — |
| 3 | design | `/design` | `proposal.md` | `docs/spec.md`, `docs/acceptance.feature` | — |
| 4 | handover | `/handover` | `spec.md` | `judge/round-<n>/case.json`, `brief.md`, verdicts, `docs/ruling.md` | — |
| 5 | verdict | `/verdict` | `docs/ruling.md` | recorded judge ruling, `docs/changes.md` on revision | — |
| 6 | initiate | `/initiate` | `spec.md`, ruling | `docs/backlog.md` | **judge** |
| 7 | build | `/build` | backlog slice | code + tests; slice status in `pipeline.json` | — |
| 8 | devops | `/devops` | the working tree | CI, staging deploy, `CHANGELOG.md`, release tag | — |
| 9 | test | `/test` | code + `acceptance.feature` | `docs/test-report.md`, test gate | — |
| 10 | security | `/security` | code + deps | `docs/threat-model.md`, `docs/security-audit.md`, security gate | — |
| 11 | launch | `/launch` | a green release | production deploy, rollback drill, `docs/runbook.md` | **security** |

## Status enum

`not started | in progress | blocked | complete` — the house convention from
`.github/continuity_protocol.md`.

## Gates

| Gate | Guards | Passes when |
|---|---|---|
| judge | `initiate` | A recorded ruling of `SOUND`, or `FIX FIRST` with no fix left open |
| security | `launch` | `pk ship audit` recorded `PASS`: no secrets in files or history, dependencies clean, threat model complete |
| test | `launch` (via phase order and `pk ship done launch`) | `pk ship test` recorded `PASS`: full suite green, every scenario mapped |

`REJECT`, `SPLIT` and `NEEDS INFO` never pass a gate.

## Checkpoints

In `auto`, the pipeline pauses after `ideate`, `proposal`, `handover` and `verdict`. `manual`
pauses after every phase; `yolo` after none. The budget cap is **not** a checkpoint — it halts
the run in every mode, including `yolo`.
