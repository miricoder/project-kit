---
name: pipeline
description: Drive and inspect the Project Kit product pipeline — report which phase a project is in, what may run next, and run or offer the next skill. Also sets the run mode (manual, auto, yolo) and the budget cap. Use when the user says /pipeline, "what's next", "where are we", "resume this project", "set mode to yolo", "run the pipeline", or asks about a project's phase, gate or judge status.
---

# /pipeline

The conductor. Owns phase state, gates, run mode and the budget, and routes to the next
skill. Every other Project Kit skill reads the state this skill writes.

## Hard rules

1. **Never assert that a gate passed.** Gates are decided by `gate.py`, which exits non-zero
   and refuses. If it refuses, report the reasons verbatim and stop.
2. **Never skip a checkpoint the mode requires.** The mode is in `pipeline.json`, not your
   judgement.
3. **Record before handing off.** A phase that is not recorded `complete` did not happen, and
   the next skill will refuse.

## Commands

Project Kit ships a launcher, `bin/pk`. **Resolve its path once, then use that literal path
in every later command** — each Bash call is a fresh shell, so no variable survives between
them, and `$CLAUDE_PLUGIN_ROOT` is *not* exported into the shell environment.

```bash
# If pk is already on PATH (setup.sh --fix puts it there), just use `pk` and skip this.
command -v pk || ls -d "$HOME"/.claude/plugins/cache/project-kit/project-kit/*/bin/pk \
                       "$HOME"/.claude/skills/project-kit/bin/pk 2>/dev/null | tail -1
```

Take the path it prints and substitute it wherever this skill says `pk` below, for example:

```bash
/Users/you/.claude/plugins/cache/project-kit/project-kit/0.3.1/bin/pk gate -C . phase ideate
```

If it prints nothing, Project Kit is not installed correctly — tell the user to run
`claude plugin install project-kit` and stop.

`-C <dir>` is the project directory; omit it to use the current one.



The gate command checks the **environment** as well as pipeline state. Two outcomes
matter:

- **Exit 1** — report every reason verbatim and stop. Environment reasons carry their own
  `Fix:` command; pass it on rather than paraphrasing.
- **An `advisories` array in the output** — the phase may run, but something will break a
  later one. Tell the user now, in one line, rather than letting them discover it three
  phases in.
commands take `-C <project dir>`; omit it to use the current directory.

## Step 1: Find or create the project state

```bash
pk state -C . show
```

If it reports no `pipeline.json`, this is a new project. Ask the user for a short project name
(kebab-case), then:

```bash
pk state -C . init --project <name> --max-usd 25
```

Tell the user the budget cap you set and that `/pipeline` can change it.

## Step 2: Report where things stand

```bash
pk state -C . next
```

Report, in this shape:

    PROJECT  <name>          Mode: <mode>    Budget: $<spent> / $<max>
    Phase:   <phase> — <status>
    Next:    <resume_point>
    Blocked: <blockers, if any>

## Step 3: Run or offer the next phase

Check first — never skip this:

```bash
pk gate -C . phase <next phase>
```

- **Exit 1 (refused):** report the reasons verbatim and stop. Do not invoke the next skill.
- **Exit 0:** act on the mode in the output:

| Mode | What you do |
|---|---|
| `manual` | **Present a menu** of what can run next and stop. Let the user pick. Do not invoke anything. |
| `auto` | Invoke the next skill via the Skill tool. After it finishes, stop if it was a checkpoint phase (`ideate`, `proposal`, `handover`, `verdict`), otherwise continue to the next. |
| `yolo` | Invoke the next skill and keep going, with no stops, until a gate refuses, the budget trips, or every phase is complete. |

The phase-to-skill mapping is one to one: phase `design` is the `design` skill.

**Before `design`, `handover` or `verdict` runs** (and whenever a gate refuses on the judge
panel), ask for a judge key: follow `references/judge-keys.md`. It asks the user, with the
AskUserQuestion tool, for at least one non-Anthropic API key and how to fill the remaining
seats, in every mode including `yolo`. Asking before `design` is what lets the rest of a
`yolo` run go unattended. A judging round never starts without at least one key, unless
the user explicitly chose an all-paste panel.

## Step 4: Record what happened

After each skill reports a deliverable:

```bash
pk state -C . phase <phase> complete --artifact <path> [--artifact <path>]
```

Use `in progress` when starting long work and `blocked --reason "<why>"` when you cannot
proceed — a blocked phase is reported by `next` instead of being silently skipped.

Judge rulings are recorded by `/verdict`, not here.

## Skipping the judge round

The user may skip judging, for example when no judge key works or they accept the risk of
an unjudged plan. Only on their explicit request, never on your own initiative and never as
a way round a failing ruling you were not asked to drop:

```bash
pk state -C . waive judge --reason "<the user's reason, in their words>"
```

This records the judge gate as `WAIVED` with that reason, marks `handover` and `verdict`
complete with a `skipped` note, and lets `/initiate` run. Say plainly that the plan goes
into development unjudged. Only the judge gate can be waived; the security gate cannot.

## Setting the mode

```bash
pk state -C . mode            # report
pk state -C . mode yolo       # set
```

When setting `yolo`, **always** also run:

```bash
pk gate harness
```

If `unattended_ready` is false, tell the user plainly: Project Kit will not stop, but Claude
Code will still prompt for the permissions in `missing_allow`, so the run is not actually
unattended until those are allowlisted in `~/.claude/settings.json`. Never describe `yolo` as
hands-off without checking this.

## Budget

```bash
pk state -C . budget                 # report
pk state -C . budget --max 50        # raise the ceiling
pk state -C . budget --add 1.80      # record spend (the panel does this)
```

An exceeded budget blocks every phase. It is not a checkpoint and `yolo` does not bypass it:
the run halts and reports. The user may raise the ceiling and continue.

## Resuming

State is written after every phase, so a new session resumes from `pipeline.json`. Run Step 1
then Step 2 and continue — never restart a project from the beginning because context was
lost.

## Phases

See `references/phases.md` for each phase, its owner skill, inputs, outputs and gate.
`ideate` → `initiate` are implemented; `build` onward are declared in state and have no skill
yet.

`/remediate` is not a phase: it drives `handover` and `verdict` in a loop, fixing what
`pk qa` and the judges find, until everything passes. In `yolo` mode `/design` hands over to
it. It ends by invoking `/initiate`, which always asks before development starts.
