---
name: verdict
description: Read the judge panel's ruling, record it in the pipeline, and act on it — open the judge gate on SOUND, or rank the open fixes, send each back to the phase that owns it, and bound the re-judge rounds. Use when the user says /verdict, "what did the judges say", "read the ruling", "did it pass", or after /handover completes.
---

# /verdict

Turn the panel's ruling into the next action. The ruling itself is already decided — by
three judges and a combination rule in code. Your job is to record it, explain it plainly,
and, if it did not pass, route each fix back to the phase that owns it.

## Hard rules

1. **The ruling is not yours to change.** Do not argue with it, soften it, or re-rank the
   fixes. `docs/ruling.md` is generated; quote it. If you think a judge is wrong, say so as
   your opinion, after the ruling, and let the user decide whether to answer it in
   `docs/changes.md` for the next round.
2. **Only a recorded ruling opens the gate.** `pk judge record` re-derives the ruling from
   the raw replies and refuses a mismatch. Never write a ruling into `pipeline.json` any
   other way.
3. **Open fixes close by re-judging, not by assertion.** There is no command that marks a fix
   done. Revise, write `docs/changes.md`, and run `/handover` again.
4. **Rounds are bounded.** After three, stop and ask. Pass `--allow-extra-round` only when
   the user has said so in this conversation.

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
/Users/you/.claude/plugins/cache/project-kit/project-kit/0.4.0/bin/pk judge -C . record
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

## Step 1: Gate

```bash
pk gate -C . phase verdict
pk state -C . phase verdict "in progress"
```

## Step 2: Record the ruling

```bash
pk judge -C . record
```

It prints `ruling`, `passed`, `open_fixes`, `rounds_left` and `next`. Refusals:

- **The plan changed after it was judged** — someone edited `docs/` during handover. The
  ruling is for a version that no longer exists: send the user back to `/handover`.
- **ruling.json disagrees with the verdicts** — re-run `pk judge -C . combine`, then record.
- **Past the round limit** — stop and ask the user whether to judge again (Step 6).

## Step 3: Read the ruling

Read `docs/ruling.md` in full: the panel, what each judge rated on every criterion, the
open fixes in rank order, dissent, recommended and minor findings, and questions.

## Step 4: Tell the user

    VERDICT  <project>  round <n>
    Ruling:  <ruling>   Judge gate: <passed / closed>
    Panel:   <family> <verdict> · <family> <verdict> · <family> <verdict>
    Open fixes (<n>), most important first:
      1. <id> — <claim>  → <phase that owns it>
    Questions: <n>   Dissent: <who, which way>
    Rounds left: <rounds_left>
    Full ruling: docs/ruling.md

The **phase that owns a fix** is the earliest one whose document must change:

| The fix changes… | Owner |
|---|---|
| who it is for, the job, prior art, an assumption | `ideate` (docs/research.md) |
| what v1 includes or excludes, phases, cost, effort | `proposal` (docs/proposal.md) |
| architecture, data, interfaces, failure modes, rollback, security, scenarios | `design` (docs/spec.md, docs/acceptance.feature) |

A `SPLIT` is always owned by `proposal`. A `NEEDS INFO` question goes to the user first: only
they can answer most of them.

## Step 5a: Passed

```bash
pk state -C . phase verdict complete --artifact docs/ruling.md
pk gate -C . gate judge
pk state -C . next
```

The gate check must exit 0. Mention the recommended and minor findings: they do not hold the
gate, and are worth carrying into the build. Then invoke `initiate` via the Skill tool in
every mode: its first step asks the user whether to start development, so nothing starts
without their yes.

If the user would rather not fix and re-judge round by round, `/remediate` runs the whole
fix → re-check → re-judge loop unattended.

## Step 5b: Not passed — checkpoint

In `manual` and `auto`, ask plainly: **revise and re-judge, or stop here?** and wait. In
`yolo`, revise without asking while rounds remain and the budget allows.

To revise:

1. **Reopen the earliest owning phase** and reset everything after it up to `verdict`.
   For a design-only revision:

   ```bash
   pk state -C . phase design "in progress"
   pk state -C . phase handover "not started"
   pk state -C . phase verdict "not started"
   ```

   If `proposal` owns a fix, reopen `proposal` and reset `design` as well; if `ideate` does,
   reopen `ideate` and reset everything after it.
2. **Revise through the owning skill** (`/proposal` or `/design`), so its own rules, checks
   and precision pass apply. Get the user's answers to any questions first.
3. **Write `docs/changes.md`** before handing over again: one entry per open fix id from the
   last ruling, saying what changed and where, or why it was not changed. Answer every
   question. The next `pk judge case` refuses if an open fix id is missing from it, and the
   judges are told not to re-raise a fix that this file shows was settled.
4. **Run `/handover`** for the next round.

`REJECT` deserves a direct conversation, not an automatic revision: the judges are saying
the core does not work. Offer three options — revise substantially, go back to `/proposal`
and re-scope, or stop the project — and let the user choose, in every mode.

## Step 6: Out of rounds

When `rounds_left` is 0 and the gate is closed, stop in every mode. Tell the user how many
rounds ran, what is still open, and that another round costs about the same as the last
(`spend_usd` in `judge/round-<n>/ruling.json`). Only if they agree:

```bash
pk judge -C . case --allow-extra-round
```

and later `pk judge -C . record --allow-extra-round`.
