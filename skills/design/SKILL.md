---
name: design
description: Turn an accepted proposal into a full-stack technical spec plus executable Gherkin acceptance criteria — architecture, data model, interfaces, failure modes and rollback. The last phase before the independent judge panel. Use when the user says /design, "design this", "write the spec", "how should this be built", or after /proposal is accepted.
---

# /design

Produce the artefact the judges will attack. Everything here must be specific enough to be
wrong — a spec vague enough to be unfalsifiable will come back `NEEDS INFO` and cost you a
panel round.

## Hard rules

1. **Decisions, with the alternative named.** Every significant choice records what else
   was considered and why it lost. A decision with no rejected alternative was not a decision.
2. **Acceptance criteria are executable.** Gherkin scenarios in `docs/acceptance.feature`.
   `/test` later maps tests to these, so vagueness here becomes an untestable product.
3. **Failure modes are part of the design.** What happens on interruption, bad input,
   concurrent use, a failed dependency. Judges probe exactly here.
4. **Rollback before launch.** How a bad release is undone — including data. `git revert`
   does not undo a schema migration.
5. **Reuse what is proven before inventing.** Check the user's existing repositories for a
   working pattern and cite it rather than designing a new one.

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
## Step 1: Gate

```bash
pk gate -C . phase design
pk state -C . phase design "in progress"
```

Exit 1: report verbatim and stop.

Then make sure the judges will be able to sit when this design is finished:

```bash
pk keys status
```

If `ready` is false, ask for a judge key now, before designing: follow
`../pipeline/references/judge-keys.md` (the user is asked with the AskUserQuestion tool for
at least one non-Anthropic API key, stored by them with `pk keys add <family>`, never typed
into the chat). Asking here, not after the spec is written, is what lets `auto` and `yolo`
run on to the judges without stopping. If the user declines, design anyway and say that
judging will wait for a key.

## Step 2: Read the proposal

Read `docs/proposal.md` and `docs/research.md`. The v1 cut and the out-of-scope list are
binding. If the design needs something the proposal excluded, that is a scope change: say
so and send the user back to `/proposal` rather than quietly widening scope.

## Step 3: Look for proven patterns first

Before choosing a stack, look at what the user already runs successfully. A pattern that
already works in their world beats a better one they have never operated. Cite the file you
found it in.

## Step 4: Design

Cover, in this order:

1. **Architecture** — components and what each owns. One diagram, in text.
2. **Data model** — entities, fields, relationships, and *where the data physically lives*.
   Include schema versioning and migration from day one.
3. **Interfaces** — the API or module boundaries other code depends on.
4. **Failure modes** — a table of what can go wrong and what the system does.
5. **Rollback** — code and data, separately.
6. **Security and privacy** — what is sensitive, where secrets live, what is logged.

## Step 5: Write the Gherkin acceptance criteria

Write `docs/acceptance.feature`. See `references/gherkin-guide.md`. Cover the happy path for
**the one thing**, plus every failure mode in the table. A failure mode with no scenario is
a failure mode nobody will test.

## Step 6: Write spec.md

Write `docs/spec.md` from `references/spec-template.md`.

## Step 7: Draft the counter-argument

The judges need the strongest case that this design is **wrong** — the most plausible
failure, not a strawman. Write it into the spec's final section. If you authored the design,
argue against it harder, not softer. This is carried into the judge case by `/handover`.

## Step 8: Precision check

Map every v1 capability from the proposal to a section of the spec and at least one Gherkin
scenario. Report anything unmapped rather than claiming completion.

## Step 9: Record and hand off

```bash
pk state -C . phase design complete \
  --artifact docs/spec.md --artifact docs/acceptance.feature
pk state -C . next
```

Report:

    DESIGN  <name>
    Architecture: <one line>
    Data:         <store> — <n> entities, migrations <yes/no>
    Scenarios:    <n> across <m> features
    Failure modes: <n> — all with scenarios: <yes/no>
    Rollback:     code <yes/no>  data <yes/no>
    Written: docs/spec.md, docs/acceptance.feature

Then:

- **`manual`** — stop and offer `/handover`, or `/remediate` to loop to green unattended.
- **`auto`** — `design` is **not** a checkpoint. Invoke `handover` via the Skill tool. It
  has its own checkpoint before spending anything.
- **`yolo`** — invoke `remediate`: it checks, fixes, judges and re-judges until everything
  passes, then hands over to `/initiate`.
