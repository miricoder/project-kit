# PANKRA — design package for Project Kit

PANKRA (from *pankration*, "all strength", the original hybrid sport) is the all-in-one iOS
and web app for hybrid athletes: training plans as whiteboard cards, result logging and
analysis, Hyrox race breakdowns, rescheduling around box classes, paces per machine, fuel,
Instagram posts, with session music planned as future R&D. Every AI job is a skill, agent or plugin from
[`registry/`](../../registry/README.md), run on Claude or GPT.

This folder is the **design input** Project Kit pulls to build and deploy the app. It is not
a project directory: Project Kit refuses to run its pipeline inside its own source tree
(`plugin_root_of` in `skills/pipeline/scripts/state.py`), so the app is built in its own
repository.

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

## How Project Kit picks this up

From a Claude Code session with the Project Kit plugin installed:

```bash
# 1. A dedicated repository for the app (empty), e.g. miricoder/pankra
gh repo create miricoder/pankra --private --clone && cd pankra

# 2. Bring the design in from this branch of project-kit
git -C /tmp clone --depth 1 -b app/pankra-design https://github.com/miricoder/project-kit pk-src
mkdir -p docs && cp /tmp/pk-src/apps/pankra/docs/* docs/

# 3. Import the design: copies docs/ and marks ideate, proposal and design complete
pk state -C . import /tmp/pk-src/apps/pankra --project pankra
pk state -C . next          # -> handover (the judge panel)

#    Or skip the panel and go straight to the backlog and build:
pk state -C . import /tmp/pk-src/apps/pankra --project pankra --skip-judge "<reason>"
pk state -C . next          # -> /initiate, then /build
```

The judge panel is the default but optional. Skipping it is recorded as `WAIVED` with your
reason and shown everywhere the ruling would be; running `/handover` later replaces it.

Runtime skills come from this repository's `registry/` at `REGISTRY_REF` (see
`docs/spec.md`, "Registry sync"). Nothing in `registry/` needs copying.

## Before the build can deploy

Read `docs/inputs-checklist.md`. Project Kit can write and test everything without it, but
stops at each deploy step until the matching item is in place.
