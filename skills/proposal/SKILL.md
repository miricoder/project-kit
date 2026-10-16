---
name: proposal
description: Turn research into a scoped proposal — what v1 is, what it explicitly is not, what it costs and how long it takes. The scope-and-money decision point of the Project Kit pipeline. Use when the user says /proposal, "scope this", "what would v1 be", "cut this down", or after /ideate completes.
---

# /proposal

Decide what gets built. This is the phase where scope is cut, and the cut is the
deliverable — a proposal that says yes to everything is not a proposal.

## Hard rules

1. **Out-of-scope is mandatory and specific.** "Advanced features" is not out-of-scope.
   "No multi-user sharing, no cloud sync, no export to PDF" is.
2. **Do not design.** Still no architecture. Cost estimates need a rough shape, not a stack.
3. **Cost must be stated even when uncertain.** Give a range and name what drives it. "It
   depends" is not an estimate.
4. **This is a checkpoint in every mode except `yolo`.** The user accepts the scope, not you.

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
pk gate -C . phase proposal
```

Exit 1: report the reasons verbatim and stop. The usual cause is that `/ideate` has not
completed, which means there is no `docs/research.md` to scope from.

```bash
pk state -C . phase proposal "in progress"
```

## Step 2: Read the research

Read `docs/research.md` in full. Pay attention to **the one thing** and to the open
questions — an open question that would change the scope must be resolved here or carried
forward explicitly as a risk.

## Step 3: Cut v1 to the one thing

Start from the job, not the feature list. The v1 cut is the smallest thing that does the
job end to end for one person. Everything else is a later phase or out of scope.

A useful test: if you removed any single item from v1, would the job still get done? If yes,
that item is not v1.

## Step 4: Phase the rest

Phases are numbered from 0, Phase 0 being foundation. Each phase gets **acceptance
criteria** — observable conditions, not activities. "Transactions import" is an activity;
"a CSV of 500 rows imports in under 5s with every row categorised or flagged" is a criterion.

## Step 5: Estimate cost and effort

Two kinds of cost, both stated:

- **Build effort** — rough working sessions per phase. A range, not a point.
- **Running cost** — hosting, model API spend, app-store fees, domains. If the product
  calls a model, estimate per-use cost and say what drives it.

Name the single biggest uncertainty in the estimate.

## Step 6: Write proposal.md

Write `docs/proposal.md` from `references/proposal-template.md`.

## Step 7: Precision check

Map each requirement from the research to a section you wrote, or to the explicit
out-of-scope list. Anything unmapped gets said out loud, not quietly dropped.

## Step 8: Record and hand off

```bash
pk state -C . phase proposal complete --artifact docs/proposal.md
pk state -C . next
```

Report:

    PROPOSAL  <name>
    v1:        <one line>
    Phases:    <n>  (Phase 0 … Phase <n-1>)
    Not doing: <the three biggest exclusions>
    Effort:    <range>      Running cost: <range>
    Biggest unknown: <one line>
    Written: docs/proposal.md

Then:

- **`manual`** and **`auto`** — this is a checkpoint. Ask the user plainly: *accept this
  scope and cost?* and **wait**. If they cut or add, revise and re-present; do not proceed
  on a scope they have not accepted.
- **`yolo`** — invoke `design` via the Skill tool.
