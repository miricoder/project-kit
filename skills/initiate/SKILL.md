---
name: initiate
description: Start development once the judge gate is open — ask the user for approval, then turn the approved spec and acceptance criteria into an ordered backlog of build slices, each tied to the scenarios that prove it done. Judge-gated. Use when the user says /initiate, "start development", "start building", "make the backlog", or when /remediate or /verdict finishes with the gate open.
---

# /initiate

The doorway from planning to building. Nothing is built here: you confirm the user wants
development to begin, and turn the approved plan into slices small enough to build and test
one at a time.

## Hard rules

1. **Always ask before starting development — in every mode, `yolo` included.** This is the
   one approval the pipeline never skips. No answer, no backlog.
2. **The gate decides, not you.** `pk gate phase initiate` refuses unless the judge gate has
   a recorded pass, or the user waived it. Never work around it.
3. **The backlog covers the plan exactly.** Every acceptance scenario lands in a slice;
   nothing outside the proposal's v1 cut is added. `pk qa backlog` checks the first.

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
/Users/you/.claude/plugins/cache/project-kit/project-kit/0.5.0/bin/pk gate -C . phase initiate
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
pk gate -C . phase initiate
```

Exit 1: report verbatim and stop. A closed judge gate sends the user to `/remediate`.

## Step 2: Ask

Show, then **wait for an explicit yes**:

    READY TO BUILD  <project>
    Judge ruling:  <ruling>, round <n>   (docs/ruling.md)
                   or: WAIVED, not judged (<waived_reason>)
    Checks:        all passed            (qa/report.json)
    v1:            <the proposal's one-sentence v1>
    Slices:        about <n>, from the proposal's phases
    Spent so far:  $<spent> of $<max>

    Start development? This writes docs/backlog.md and then offers to build slice 1.

Anything but a clear yes: stop, and say `/initiate` picks up from here.

## Step 3: Write the backlog

```bash
pk state -C . phase initiate "in progress"
```

Write `docs/backlog.md`:

```markdown
# Backlog: <project>

> From docs/spec.md and docs/acceptance.feature, judged <ruling> in round <n>.
> (Waived: "not judged: the judge round was skipped at the user's request".)
> Order is build order. A slice is done when its scenarios pass.

## Slice 1: <name>
- **Delivers:** <the user-visible capability>
- **Proposal phase:** <n>
- **Scenarios:** <exact scenario names from docs/acceptance.feature>
- **Touches:** <components and data from the spec>
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes
```

Order by the proposal's phases; inside a phase, the slice the others depend on first. Keep
each slice to one or two working sessions. Carry the ruling's `recommended` findings into the
slice they belong to; a waived gate has none.

## Step 4: Check coverage, fix until it passes

```bash
pk qa -C . backlog
```

Every scenario must be in a slice. Fix and re-run until it exits 0; no need to ask.

## Step 5: Record and offer slice 1

```bash
pk state -C . phase initiate complete --artifact docs/backlog.md
pk state -C . next
```

    BACKLOG  <project>   <n> slices, <m> scenarios covered
    Slice 1: <name> — <delivers>
    Start building slice 1?

On yes: build it test-first — write its scenarios as automated tests, implement until they
pass, then `pk qa -C .`. (`/build`, which will own this step, is planned; until it ships this
is done directly.)
