# PANKRA — design package for Project Kit

PANKRA (from *pankration*, "all strength", the original hybrid sport) is the all-in-one iOS
and web app for hybrid athletes: training plans as whiteboard cards, result logging and
analysis, Hyrox race breakdowns, rescheduling around box classes, paces per machine, fuel,
Instagram posts and session music. Every AI job is a skill, agent or plugin from
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

# 3. Start the pipeline at the judge gate: the design phases are already written
pk state -C . init --project pankra
pk state -C . phase ideate complete --artifact docs/research.md
pk state -C . phase proposal complete --artifact docs/proposal.md
pk state -C . phase design complete --artifact docs/spec.md --artifact docs/acceptance.feature
pk state -C . next          # -> handover: /handover, then /verdict, /initiate, /build, ...
```

Marking the first three phases complete records that their artefacts exist; it opens no
gate. The judge gate before `/initiate` still needs a recorded ruling from `/handover` and
`/verdict`.

Runtime skills come from this repository's `registry/` at `REGISTRY_REF` (see
`docs/spec.md`, "Registry sync"). Nothing in `registry/` needs copying.

## Before the build can deploy

Read `docs/inputs-checklist.md`. Project Kit can write and test everything without it, but
stops at each deploy step until the matching item is in place.
