# Phases

Order is pipeline order. `next` returns the first phase that is not `complete`.

| # | Phase | Skill | Reads | Writes | Gate before it |
|---|---|---|---|---|---|
| 1 | ideate | `/ideate` | the user's idea | `docs/research.md` | — |
| 2 | proposal | `/proposal` | `research.md` | `docs/proposal.md` | — |
| 3 | design | `/design` | `proposal.md` | `docs/spec.md`, `docs/acceptance.feature` | — |
| 4 | handover | `/handover` | `spec.md` | `judge/<run>/case.json`, `brief.md`, verdicts | — |
| 5 | verdict | `/verdict` | verdicts | `docs/ruling.md`, recorded judge ruling | — |
| 6 | initiate | `/initiate` | `spec.md`, ruling | `docs/backlog.md` | **judge** |
| 7 | build | `/build` | backlog slice | code + unit tests | — |
| 8 | devops | `/devops` | the working tree | branches, PRs, releases, tags | — |
| 9 | test | `/test` | code + `acceptance.feature` | test report | — |
| 10 | security | `/security` | code + deps | threat model, audit | — |
| 11 | launch | `/launch` | a green release | soft launch, rollback drill | **security** |

## Status enum

`not started | in progress | blocked | complete` — the house convention from
`.github/continuity_protocol.md`.

## Gates

| Gate | Guards | Passes when |
|---|---|---|
| judge | `initiate` | A recorded ruling of `SOUND`, or `FIX FIRST` with no fix left open |
| security | `launch` | A recorded clean `/security` result |
| test | reported by `/test` | Full suite green with acceptance criteria mapped |

`REJECT`, `SPLIT` and `NEEDS INFO` never pass a gate.

## Checkpoints

In `auto`, the pipeline pauses after `ideate`, `proposal`, `handover` and `verdict`. `manual`
pauses after every phase; `yolo` after none. The budget cap is **not** a checkpoint — it halts
the run in every mode, including `yolo`.
