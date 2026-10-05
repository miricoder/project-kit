# Project Kit

A Claude Code plugin that takes an idea from research to a launched product, with an
**independent cross-model judge gate** before development is allowed to start.

Twelve skills compose into one pipeline. Each skill reads shared state, refuses to run if its
preconditions are unmet, does its work, records what it produced, then hands off. Gates are
enforced by scripts — not by a model asserting that a gate passed.

- 📖 **[Pipeline docs](https://miricoder.github.io/project-kit/)** — skill-by-skill detail, the flow, phase interaction
- 📊 **[Know-how and project tracker](https://miricoder.github.io/project-kit/project_kit_know_how.html)** — install guide and the status of every project you have run through it

## Requirements

- **Claude Code 2.x or newer.** Plugin support is required. Check with `claude --version`; if
  you are on a 0.x or 1.x build, upgrade with `npm i -g @anthropic-ai/claude-code@latest`.
- `python3` — the gate and state logic is pure Python standard library.
- For the judge gate: access to **three different model families**, at least one as an API
  key. See [Judge panel setup](#judge-panel-setup).

## Install

```bash
claude plugin marketplace add miricoder/project-kit
claude plugin install project-kit
```

Then `/reload-plugins`, or start a new session. Verify:

```bash
claude plugin details project-kit
```

To update later: `claude plugin update project-kit`.

## Quick start

```
/ideate I want an app that tracks my houseplants and tells me when to water them
```

That is enough. `/ideate` researches the idea, frames the user and the job, surfaces the
questions that need answering, and hands off down the pipeline. Or drive it explicitly:

```
/pipeline              # report current phase and run or offer the next skill
/pipeline mode auto    # set the run mode (manual | auto | yolo)
/pipeline run --to design
```

## The pipeline

| Skill | Phase | Owns | Status |
|---|---|---|---|
| `/pipeline` | all | Phase state, gates, artifact registry, routing, resume, run mode | ✅ |
| `/ideate` | RND | Idea research, prior art, user and job framing, open questions | ✅ |
| `/proposal` | RND | Scope, v1 cut, explicit out-of-scope, cost estimate | ✅ |
| `/design` | Design | Full-stack design, technical spec, Gherkin acceptance criteria | ✅ |
| `/handover` | Handover | Builds the judge case and brief, runs the panel, validates verdicts | ✅ |
| `/verdict` | Approval | Reads the ruling, ranks fixes, back-propagates, admins rounds | ✅ |
| `/initiate` | Initiation | **Judge-gated.** Approved spec → feature backlog | planned |
| `/build` | Build | Implements one backlog slice: code plus unit tests | planned |
| `/devops` | DevOps | Repo, branches, PRs, releases, tags, CHANGELOG, CI, migrations | planned |
| `/test` | Testing | Pre-release gate: suite, coverage, acceptance-criteria verification | planned |
| `/security` | Security | Threat model, secret-in-history check, dependency audit | planned |
| `/launch` | Launch | Soft launch, rollback drill, hotfix path, observability | planned |

Three hard gates: the **judge gate** guards `/initiate`; the **test gate** and **security
gate** guard `/launch`.

## Run modes

Set once; stored in the project's `pipeline.json` and persists across sessions.

| Mode | Behaviour |
|---|---|
| `manual` | Stops after **every** skill and presents a menu of what can run next |
| `auto` *(default)* | Advances between phases, stopping at four checkpoints |
| `yolo` | Allow-all. End to end with no pipeline stops, subject to the budget cap |

The four `auto` checkpoints: after `/ideate` (is this the idea?), after `/proposal` (accept
scope and cost?), before the panel runs (this spends API credit), and after `/verdict` (accept
the ruling, or revise and re-judge?).

### Two layers of autonomy

`yolo` removes Project Kit's own checkpoints. It **cannot** remove Claude Code's tool
permission prompts — those are harness-level and no plugin can suppress them. For a genuinely
unattended run you also need an allowlist in your settings:

```jsonc
// ~/.claude/settings.json
{
  "permissions": {
    "allow": [
      "Bash(python3:*)",
      "Bash(git:*)",
      "Bash(gh:*)",
      "Edit",
      "Write"
    ]
  }
}
```

`/pipeline mode yolo` reports whether the harness side is configured, so the mode never *looks*
hands-off while silently waiting on a prompt.

### Budget cap

`yolo` adds no confirmation stops, but honours `budget.max_usd` in `pipeline.json`. On
exceeding it the run halts and reports. Set it as high as you like — what it rules out is an
unattended `REJECT` → re-judge → `REJECT` loop burning credit with nobody watching.

## Judge panel setup

The judge gate needs **three verdicts from three different model families**. Two rules are
enforced mechanically, not left to judgement:

1. **No family may hold two seats.** Two judges from one family share priors, producing a
   ruling that looks independent and is not.
2. **The authoring family is excluded.** Claude writes the plan, so Anthropic cannot judge it.

Each seat uses the cheapest transport available:

| Transport | When |
|---|---|
| `api_key` | A real API key exists. Fully automated |
| `cli` | A subscription-backed CLI exists — e.g. `npm i -g @openai/codex` reuses an existing ChatGPT login, no API key and no extra cost |
| `paste` | Neither. The brief is rendered for you to paste, and the returned JSON is validated before being accepted |

> A ChatGPT subscription is **not** an OpenAI API key. Using `api_key` for that seat means
> paying for API usage separately; `cli` avoids it.

## Where your data lives

| What | Where |
|---|---|
| Per-project pipeline state and gates | `<project>/pipeline.json` |
| Human-readable project snapshot | `<project>/.github/projects/<name>.md` |
| Registry of all projects, for the tracker page | `~/.claude/project-kit/registry.json` |

Project data is deliberately **not** stored in this repo. This repo is the tool.

## Development

```bash
git clone https://github.com/miricoder/project-kit
ln -s "$PWD/project-kit" ~/.claude/skills/project-kit   # auto-loads as project-kit@skills-dir
python3 -m unittest discover -s tests -t . -v
claude plugin validate . --strict
```

Release: bump `version` in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`,
then `claude plugin tag --push` — it refuses unless both agree.

## Licence

MIT
