# Roadmap

What is built, what is not, and in what order the rest should follow. Derived from the
planning done in development; kept here so it is reachable from any machine.

## Built

| Skill | Owns | Credentials |
|---|---|---|
| `/pipeline` | Phase state, gates, run modes, budget, project registry | none |
| `/ideate` | Prior art, the job, open questions → `research.md` | none |
| `/proposal` | v1 cut, explicit out-of-scope, phased acceptance criteria, cost → `proposal.md` | none |
| `/design` | Architecture, data model, failure modes, rollback, Gherkin → `spec.md`, `acceptance.feature` | none |
| `/handover` | Builds the case and brief, seats three families, collects and validates verdicts | three judge seats (keys, a CLI, or paste) |
| `/verdict` | Records the ruling, ranks fixes, back-propagates, bounds the rounds | as above |

Together: **idea → independently judged technical spec**. Up to the spec needs no
credentials at all.

## Remaining, by priority

### P1 — the judge gate (shipped in 0.4.0)

`/handover` and `/verdict`, built as planned: against recorded verdict fixtures, so the
logic is tested without a live panel. The loop guard is in place: at most three rounds
before the user must agree to another, and from round 2 the case carries the previous open
fixes plus `docs/changes.md`, which must answer every one of them. The form, the
combination rule and the record checks are in
[skills/handover/references/judge-form.md](../skills/handover/references/judge-form.md).

Still open here: the live transports are untested by design, and the default model names
in `judge.API_SPECS` need refreshing as providers rename them.

### P2 — from approved spec to code

`/initiate` (judge-gated: spec → backlog) and `/build` (implement a slice with tests).

Honest caveat: plain Claude Code already implements well from a spec. These add slice
discipline and gate enforcement, not core capability.

### P3 — professional hygiene

`/devops` (branches, PRs, releases, tags, CHANGELOG, CI, migrations) and `/test`
(pre-release gate mapping tests to the Gherkin criteria). Both replicable by hand, which
is exactly how this repository has been run so far.

### P4 — deprioritised

`/security` — Claude Code already ships a `security-review` skill, so marginal value is
lowest of the set. `/launch` — only matters once something real exists to ship, and cannot
be called complete until a rollback has been rehearsed against a real release.

## The MVP cut

**Built four + P1 — now done.** Idea → independently judged technical spec is a coherent
product on its own. Implementation can proceed with plain Claude Code while P2 and P3 follow.

## Also deferred

Exposing the pipeline through a GitHub Action, the VS Code Marketplace, and Copilot
Extensions. Of those the **Action is the only one that preserves mechanical gates** — the
gate scripts are pure Python with meaningful exit codes, which is what a CI check is. A
Copilot Extension cannot run them locally, so it would be advisory only; if built, it must
be labelled as such rather than presented as authoritative.
