# PANKRA — design package for Project Kit

PANKRA (from *pankration*, "all strength", the original hybrid sport) is the all-in-one iOS
and web app for hybrid athletes: training plans as whiteboard cards, result logging and
analysis, Hyrox race breakdowns, rescheduling around box classes, paces per machine, fuel,
Instagram posts, with session music planned as future R&D. Every AI job is a skill, agent or plugin from
[`registry/`](../../registry/README.md), run on Claude or GPT.

This folder is the **PANKRA project**: the design is in `docs/`, and Project Kit builds
the app here, in this same folder of the project-kit repository.

## Files

| File | Pipeline phase | What it holds |
|---|---|---|
| `docs/research.md` | ideate | The job, prior art, open questions |
| `docs/proposal.md` | proposal | v1 cut, exclusions, phases, cost |
| `docs/spec.md` | design | Architecture, decisions, data model, interfaces, failure modes, rollback, security, Apple deployment |
| `docs/acceptance.feature` | design | Gherkin acceptance criteria |
| `docs/inputs-checklist.md` | before build | Everything the owner must provide, and how |

The full illustrated design (diagrams of the architecture and the skills graph) is the Claude
doc "PANKRA: end-to-end design". This folder is the version Project Kit works from; where
they differ, this folder wins.

## How to build it

In a Claude Code session on the `miricoder/project-kit` repository (the Project-Kit cloud
environment installs the plugin), send:

```
/project-kit:build apps/pankra
```

`/build` sets the project up in this folder (`pk state import apps/pankra`), asks once
whether to run the judge panel or skip it, runs `/initiate` (which asks before writing
`docs/backlog.md`), then builds slice by slice, committing to this repository. To pick up
later, send the same command: progress lives in `apps/pankra/pipeline.json`.

Runtime skills come from this repository's `registry/` at `REGISTRY_REF` (see
`docs/spec.md`, "Registry sync"). Nothing in `registry/` needs copying.

## Before the build can deploy

Read `docs/inputs-checklist.md`. Project Kit can write and test everything without it, but
stops at each deploy step until the matching item is in place.
