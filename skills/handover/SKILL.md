---
name: handover
description: Send the finished plan to the independent judge panel — build the case and brief from the research, proposal, spec and acceptance criteria, seat three judges from three different model families (never Anthropic), collect and validate each verdict. Stops before spending anything. Use when the user says /handover, "send it to the judges", "judge the plan", "run the panel", or after /design completes.
---

# /handover

Put the plan in front of three judges who did not write it. You build the case, run the
panel and check every reply against the form. You do **not** judge, summarise or soften
what the judges said: the ruling is combined by a script, and `/verdict` explains it.

## Hard rules

1. **Never judge the plan yourself.** Claude wrote it. Anthropic cannot hold a seat, and no
   verdict of yours counts. If the panel cannot sit, say so and stop; do not fill the gap.
   The user may instead choose to skip the round (`pk state waive judge`, see
   `../pipeline/SKILL.md`), which records it as waived, not judged.
2. **Stop before spending.** In every mode except `yolo`, show the seats and the estimated
   cost and wait for the user to agree. This is a checkpoint even in `auto`.
3. **Never edit a judge's reply.** An invalid reply is sent back to that judge with the
   validator's exact problems, or the seat is re-run. You do not repair the JSON.
4. **Never edit the plan during handover.** `pk judge record` rebuilds the case from `docs/`
   and refuses a ruling for a version that no longer exists. Revisions belong to `/verdict`.

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
/Users/you/.claude/plugins/cache/project-kit/project-kit/0.4.0/bin/pk judge -C . status
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

`pk judge` follows the same contract: exit 1 is a refusal with reasons; report them verbatim.

## Step 1: Gate

```bash
pk gate -C . phase handover
pk state -C . phase handover "in progress"
```

Exit 1 usually means `/design` is not complete, or the panel has fewer than three seats.
For a short panel, do not just pass the `Fix:` on: ask for a judge key, following
`../pipeline/references/judge-keys.md`. The user is asked with the AskUserQuestion tool for
at least one non-Anthropic API key, which they store themselves with
`pk keys add <family>`, and the remaining seats become paste seats with
`pk keys paste-rest`. Then run the gate again. A round does not start without at least one
key unless the user explicitly asks for an all-paste panel.

## Step 2: Build the case

```bash
pk judge -C . case
```

This writes `judge/round-<n>/case.json` and `brief.md`: the rules, the form, the whole plan
and, from round 2, the previous open fixes with `docs/changes.md`. It refuses if a document
is missing, if `docs/spec.md` has no real counter-argument, or if `docs/changes.md` does not
answer every open fix from the last round. Fix the cause and re-run; do not work around it.

## Step 3: Seat the panel

```bash
pk judge -C . seats
```

Three families, each with its transport: `api_key` (billed), `cli` (subscription, no
spend) or `paste` (the user carries the brief). `--seat <family>` three times picks the
panel explicitly; `--paste <family>` forces pasting even where a key exists.

## Step 4: Checkpoint — before anything is spent

Show the user, then **wait** (skip only in `yolo`):

    HANDOVER  <project>  round <n>
    Case:     <case_id>   brief <brief_chars> characters
    Seats:    <family> (<transport>), <family> (<transport>), <family> (<transport>)
    Cost:     ~$<estimate> from the API seats   Budget: $<spent> / $<max>
    Paste:    <families the user will paste for, if any>
    Proceed?

Take `estimate_usd` and `budget` from the `seats` output (it prints them once the case
exists). It is an estimate from published per-token rates, deliberately on the high side;
say so.

## Step 5: Run the panel

```bash
pk judge -C . run
```

- **API and CLI seats** are called now. Each reply is stored under `judge/round-<n>/raw/`
  and validated; spend is added to the budget as it happens.
- **Paste seats** are listed with what to do. Tell the user, per family: open that
  family's chat, paste the whole of `judge/round-<n>/brief.md`, save the reply to a file,
  then give you the path. Accept it with:

  ```bash
  pk judge -C . accept --family <family> --file <path> --model "<model they used>"
  ```

- **A refusal on budget** names the estimate and the cap. Ask the user; raise the cap only
  if they say so (`pk state -C . budget --max <usd>`).
- **A failed seat** (network, no credit) is reported with its reason. Re-run just that seat
  with `pk judge -C . run --seat <family> --seat <…> --seat <…>` after the cause is fixed.

## Step 6: Every reply valid

```bash
pk judge -C . status
```

For an invalid reply, send that judge the listed problems word for word and ask for a
corrected reply in the same format, then `accept` (paste) or re-run (API, once). Do not
correct it yourself. When `ready_to_combine` is true, continue.

## Step 7: Combine

```bash
pk judge -C . combine
```

This writes `judge/round-<n>/ruling.json` and `docs/ruling.md`. Use `--tier high` only if
the user asks for it; greenfield plans use the default `standard` (see
`references/judge-form.md`).

## Step 8: Record and hand off

```bash
pk state -C . phase handover complete \
  --artifact judge/round-<n>/case.json --artifact judge/round-<n>/brief.md \
  --artifact docs/ruling.md
pk state -C . next
```

Report only what the script printed:

    HANDOVER  <project>  round <n>
    Panel:    <family> <verdict> · <family> <verdict> · <family> <verdict>
    Ruling:   <ruling>  (gate would <pass/stay closed>)
    Open fixes: <n>
    Spent:    $<this round>   Budget: $<spent> / $<max>
    Written:  docs/ruling.md

Then:

- **`manual`** — stop and offer `/verdict`.
- **`auto`** — `handover` is a checkpoint: show the summary and wait for the user before
  `/verdict`.
- **`yolo`** — invoke `verdict` via the Skill tool.

The ruling is not recorded in `pipeline.json` until `/verdict` runs `pk judge record`.
