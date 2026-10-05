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

## Paths

```bash
PK="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/skills/project-kit}"
STATE="$PK/skills/pipeline/scripts/state.py"
GATE="$PK/skills/pipeline/scripts/gate.py"
```

Each Bash call starts a fresh shell, so set these at the start of every command you run. All
commands take `-C <project dir>`; omit it to use the current directory.

## Step 1: Find or create the project state

```bash
python3 "$STATE" -C . show
```

If it reports no `pipeline.json`, this is a new project. Ask the user for a short project name
(kebab-case), then:

```bash
python3 "$STATE" -C . init --project <name> --max-usd 25
```

Tell the user the budget cap you set and that `/pipeline` can change it.

## Step 2: Report where things stand

```bash
python3 "$STATE" -C . next
```

Report, in this shape:

    PROJECT  <name>          Mode: <mode>    Budget: $<spent> / $<max>
    Phase:   <phase> — <status>
    Next:    <resume_point>
    Blocked: <blockers, if any>

## Step 3: Run or offer the next phase

Check first — never skip this:

```bash
python3 "$GATE" -C . phase <next phase>
```

- **Exit 1 (refused):** report the reasons verbatim and stop. Do not invoke the next skill.
- **Exit 0:** act on the mode in the output:

| Mode | What you do |
|---|---|
| `manual` | **Present a menu** of what can run next and stop. Let the user pick. Do not invoke anything. |
| `auto` | Invoke the next skill via the Skill tool. After it finishes, stop if it was a checkpoint phase (`ideate`, `proposal`, `handover`, `verdict`), otherwise continue to the next. |
| `yolo` | Invoke the next skill and keep going, with no stops, until a gate refuses, the budget trips, or every phase is complete. |

The phase-to-skill mapping is one to one: phase `design` is the `design` skill.

## Step 4: Record what happened

After each skill reports a deliverable:

```bash
python3 "$STATE" -C . phase <phase> complete --artifact <path> [--artifact <path>]
```

Use `in progress` when starting long work and `blocked --reason "<why>"` when you cannot
proceed — a blocked phase is reported by `next` instead of being silently skipped.

Judge rulings are recorded by `/verdict`, not here.

## Setting the mode

```bash
python3 "$STATE" -C . mode            # report
python3 "$STATE" -C . mode yolo       # set
```

When setting `yolo`, **always** also run:

```bash
python3 "$GATE" harness
```

If `unattended_ready` is false, tell the user plainly: Project Kit will not stop, but Claude
Code will still prompt for the permissions in `missing_allow`, so the run is not actually
unattended until those are allowlisted in `~/.claude/settings.json`. Never describe `yolo` as
hands-off without checking this.

## Budget

```bash
python3 "$STATE" -C . budget                 # report
python3 "$STATE" -C . budget --max 50        # raise the ceiling
python3 "$STATE" -C . budget --add 1.80      # record spend (the panel does this)
```

An exceeded budget blocks every phase. It is not a checkpoint and `yolo` does not bypass it:
the run halts and reports. The user may raise the ceiling and continue.

## Resuming

State is written after every phase, so a new session resumes from `pipeline.json`. Run Step 1
then Step 2 and continue — never restart a project from the beginning because context was
lost.

## Phases

See `references/phases.md` for each phase, its owner skill, inputs, outputs and gate. Wave 1
(`ideate` → `verdict`) is implemented; `initiate` onward are declared in state and will refuse
with "not implemented" until their skills ship.
