---
name: remediate
description: The yolo loop between the spec and development — check the plan, fix what fails, re-check, send it to the judge panel, apply every open fix, and re-judge, with no user intervention, until every check passes and the judge gate is open; then hand over to /initiate, which asks before any development starts. Use when the user says /remediate, "fix everything until it passes", "run it to green", "yolo it", or after /design completes in yolo mode.
---

# /remediate

Drive the plan from "spec written" to "every check passes and the judges approved it",
without stopping to ask. You find failures with `pk qa` and the judge panel, fix them in the
documents and UI files, and re-check, round after round. When everything passes you hand
over to `/initiate`, which is the one place the user is asked: whether to start development.

Invoking this skill **is** the user's permission to loop: to re-judge without the per-round
checkpoint, and to raise the judge round limit to 10. It is not permission to spend past the
budget, to widen scope, or to fake a pass.

## Hard rules

1. **Never judge, approve or mark anything passed yourself.** A check passes when `pk qa`
   says so; the judge gate passes when `pk judge record` records it. If you catch yourself
   writing "this should now pass", run the check instead.
2. **Never weaken a check to make it pass.** Do not delete a failure mode, scenario or UI
   element to silence a finding, edit a judge's reply, hand-edit `ruling.json`, or lower the
   tier. Fix the thing the check is about.
3. **Never widen scope.** The proposal's v1 cut is binding. A fix that needs more scope is
   made by cutting, never adding; record every cut in `docs/changes.md` as a scope change.
4. **Log every iteration** in `qa/remediation-log.md`: what failed, what you changed, the
   result of the re-check. It is how the user sees what happened without having watched.
5. **Stop only for a reason in Step 5.** Everything else you resolve: an unanswerable judge
   question gets the most conservative reasonable answer, marked `ASSUMED` in the document
   and listed for the user at the end.

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
/Users/you/.claude/plugins/cache/project-kit/project-kit/0.5.0/bin/pk qa -C .
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

## Step 1: Start

```bash
pk state -C . show
```

`design` must be `complete`. If it is not, say so and stop: this loop fixes a written plan, it
does not write one. Then set up the run, once:

```bash
pk state -C . mode yolo
pk judge -C . rounds 10
pk gate -C . phase handover
pk state -C . phase handover "in progress"
```

If the gate refuses on the judge panel, ask for a judge key before anything else: follow
`../pipeline/references/judge-keys.md`. This is the one question this loop asks, and it is
asked in `yolo` too, because only the user can supply a key. Once `pk keys status` shows
`ready`, run the gate again and carry on. Paste seats still need the user to carry the brief
in each round; say so. If the user declines to give any key, run Steps 2 and 3 anyway so
everything but judging is green, and stop at Step 5.

Tell the user, in one line, the budget (`pk state -C . budget`) and that you will report back
when everything passes or a stop condition is hit.

## Step 2: Check

```bash
pk qa -C .
```

It writes `qa/report.json` and exits 0 only when **every** check passes:

| Check | Fails when |
|---|---|
| `lint` | a spec section is missing or a placeholder; a failure mode names no scenario, or one not in `docs/acceptance.feature`; a decision names no rejected alternative; rollback misses code or data; a scenario has no `Then` |
| `a11y` | any UI mockup (`ui/**/*.html`, `*.dc.html`) breaks a WCAG 2.1 A/AA rule, has a tab stop with no visible focus, or scrolls sideways at 320px |
| `judge` | the judge gate has not passed |

## Step 3: Fix lint and accessibility, then re-check

Fix every `lint` and `a11y` problem in one pass, then run `pk qa -C .` again. Repeat until
both pass.

- **lint** — edit `docs/spec.md` and `docs/acceptance.feature` under `/design`'s rules: a
  failure mode gets a real scenario with a `Then`, a decision gets the alternative that
  lost, rollback covers data as well as code.
- **a11y** — fix the UI file itself: real controls instead of styled `div`s, labels, contrast,
  a visible focus indicator, wrapping text. Every write to a UI file is re-scanned by the
  plugin's hook; if it hands back failures, fix them before moving on.

The same problem failing three passes in a row is a stop (Step 5), not a fourth attempt.

## Step 4: Judge, apply the ruling, re-judge

When `lint` and `a11y` pass, run a judge round with no checkpoint (yolo):

```bash
pk judge -C . case
pk judge -C . seats
pk judge -C . run
pk judge -C . status
```

An invalid reply: re-run that seat once (`pk judge -C . run --seat <a> --seat <b> --seat <c>`,
naming the full panel). Still invalid: stop (Step 5). When `ready_to_combine` is true:

```bash
pk judge -C . combine
pk judge -C . record
```

Read `docs/ruling.md`. Then:

- **Gate passed** — go to Step 6.
- **`FIX FIRST` or `NEEDS INFO`** — make every open fix and answer every question in the
  document that owns it (the owner table in `/verdict`), rank order, then write
  `docs/changes.md`: one entry per open fix id and per question, saying what changed and
  where. Also act on `recommended` findings when the fix is inside scope. Back to Step 2.
- **`SPLIT`** — cut v1 to the first coherent product the judges described; move the rest to
  the proposal's out-of-scope list; record it as a scope change. Back to Step 2.
- **`REJECT`** — make one substantive revision aimed at the judges' core objection. A second
  `REJECT` in a row is a stop.

Do not edit anything in `docs/` between `case` and `record`: `record` refuses a ruling for a
plan that changed after it was judged.

## Step 5: Stop conditions — the only reasons to stop early

| Stop | Tell the user |
|---|---|
| Budget exceeded (`pk judge run` or any phase refuses on budget) | spent vs cap; raising it is their call: `pk state budget --max <usd>` |
| Round limit reached (`pk judge case` refuses) | rounds run, what is still open |
| The panel cannot sit: the user was asked for a judge key and gave none | that the judge gate stays shut until a key is stored with `pk keys add <family>` |
| The same check failing three passes in a row | the problem, the three attempts, why they did not work |
| A judge reply invalid twice | the validator's problems |
| Two `REJECT` rulings in a row | the core objection; this needs the user's judgement |

## Step 6: Done — prove it, then hand over

```bash
pk qa -C .
```

This must exit 0 with every check passed, including `judge`. Anything less is not done:
back to Step 2. Then record the phases the loop covered:

```bash
pk state -C . phase handover complete --artifact docs/ruling.md --artifact qa/report.json
pk state -C . phase verdict complete --artifact docs/ruling.md
pk gate -C . gate judge
```

Report:

    REMEDIATE  <project>   all checks passed
    Iterations: <n>   Judge rounds: <n>   Ruling: <ruling>
    Fixed:      <n> lint · <n> accessibility · <n> judge findings
    Assumed:    <answers you chose for unanswerable questions, or "none">
    Spent:      $<spent> of $<max>
    Log:        qa/remediation-log.md   Report: qa/report.json   Ruling: docs/ruling.md

Then invoke `initiate` via the Skill tool. It asks the user before any development starts.
