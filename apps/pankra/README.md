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
| `docs/inputs-checklist.md` | before handover and deploy | Everything the owner must provide, and when |

The full illustrated design (diagrams of the architecture and the skills graph) is the Claude
doc "PANKRA: end-to-end design". This folder is the version Project Kit works from; where
they differ, this folder wins.

## How Project Kit picks this up

`/build` is the **eighth** step, not the first. Project Kit's gates are mechanical: a phase
refuses to start until every earlier phase is complete, and `/initiate` (which writes the
backlog `/build` works from) refuses until the judge panel's ruling is recorded. Asking for
`/build` on this package straight away is therefore refused twice, by design:

| Refusal | Why | What clears it |
|---|---|---|
| `this directory is inside the Project Kit plugin` | `pk` never writes `pipeline.json` or `docs/` into its own source | Work in the app's own repository (step 1 below) |
| `handover / verdict / initiate is not started` | Building needs a judged plan and a backlog | Run steps 4–6 below, in order |

### Before you start: two things only the owner can provide

1. **An empty private repository for the app**, e.g. `miricoder/pankra`, created on GitHub
   by you. A session can only push to repositories attached to it, so tell the session its
   name and let it attach the repo.
2. **At least one judge key from a provider that is not Anthropic** (OpenAI, Google Gemini,
   Moonshot, xAI, DeepSeek or Mistral), stored by you with `pk keys add <family>`. The panel
   needs three seats from three different families; seats without a key are filled by
   pasting the brief into that provider's chat and pasting the reply back. `/handover` shows
   the estimated cost and waits for your OK before spending anything.

### Run order

```bash
# 1. In a session attached to the app repo, clone it and bring the design in from main
git clone https://github.com/miricoder/pankra && cd pankra
git -C /tmp clone --depth 1 https://github.com/miricoder/project-kit pk-src
mkdir -p docs && cp /tmp/pk-src/apps/pankra/docs/* docs/

# 2. Record the three phases this package already completes (this opens no gate)
pk state -C . init --project pankra
pk state -C . phase ideate complete --artifact docs/research.md
pk state -C . phase proposal complete --artifact docs/proposal.md
pk state -C . phase design complete --artifact docs/spec.md --artifact docs/acceptance.feature

# 3. Commit and push, so the pipeline state survives the session
git add -A && git commit -m "docs: PANKRA design package from project-kit" && git push
```

Then, as skills in the same session:

| Step | Skill | Stops for you when | Writes |
|---|---|---|---|
| 4 | `/handover` | No judge key yet; before spending (shows seats and cost) | `judge/round-1/`, verdicts |
| 5 | `/verdict` | The ruling needs fixes (then `/remediate` or a revised spec, and back to 4) | `docs/ruling.md`, the judge gate |
| 6 | `/initiate` | Always: it asks before development starts | `docs/backlog.md` (the slices) |
| 7 | `/build` | Between slices, per run mode | Code and tests, one slice at a time |
| 8 | `/devops`, `/test`, `/security`, `/launch` | Each deploy, until its item in `docs/inputs-checklist.md` is in place | CI, staging, release, production |

`pk state -C . next` always names the next step and why it is or is not runnable.

Runtime skills come from this repository's `registry/` at `REGISTRY_REF` (see
`docs/spec.md`, "Registry sync"). Nothing in `registry/` needs copying.

## Before the build can deploy

Read `docs/inputs-checklist.md`. Project Kit can write and test everything without it, but
stops at each deploy step until the matching item is in place.
