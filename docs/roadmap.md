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

Together: **idea → technical spec**, with no credentials at all.

## Remaining, by priority

### P1 — the judge gate

| Skill | Owns |
|---|---|
| `/handover` | Builds the case and brief, runs the panel, validates verdicts |
| `/verdict` | Reads the ruling, ranks fixes, back-propagates, bounds the rounds |

**Why first:** this is the differentiator. Without it, Project Kit is "Claude writes a
spec" — which Claude already does. With it, the spec has been attacked by three
independent model families. It is also the gate everything downstream depends on.

They ship together; neither is useful alone. Build against recorded verdict fixtures so
the logic is testable without a live panel.

`/verdict` owns the back-propagation loop guard: a maximum round count and a
carried-forward "what changed since last round" delta. The judge has no memory between
runs and will otherwise re-raise findings that were already settled.

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

**Built four + P1.** Idea → independently judged technical spec is a coherent product on
its own. Implementation can proceed with plain Claude Code while P2 and P3 follow.

## Also deferred

Exposing the pipeline through a GitHub Action, the VS Code Marketplace, and Copilot
Extensions. Of those the **Action is the only one that preserves mechanical gates** — the
gate scripts are pure Python with meaningful exit codes, which is what a CI check is. A
Copilot Extension cannot run them locally, so it would be advisory only; if built, it must
be labelled as such rather than presented as authoritative.
