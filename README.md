# Dumpit

Tell it your life admin in passing — "paid 42 for groceries", "move the dentist to Friday",
"Lisbon for a long weekend in March, about 600 all in" — and it files tasks, spending and
trips for you, with a dashboard you can glance at.

Planned with [Project Kit](https://github.com/miricoder/project-kit). Mode: `yolo`.

## Where things stand

| Phase | Status | File |
|---|---|---|
| ideate | complete | `docs/research.md` |
| proposal | complete | `docs/proposal.md` |
| design | complete | `docs/spec.md`, `docs/acceptance.feature` |
| remediate → judge | lint and a11y pass; **judge round skipped by the user** (gate `WAIVED`: OpenAI judge account has no credit), so the plan is unjudged | `qa/remediation-log.md` |
| initiate | complete: 13 slices, all 52 scenarios covered; building slice 1 | `docs/backlog.md` |

UI mockups: `ui/*.dc.html` (canvas: https://claude.ai/artifact/YKwgxHfyNuYxb46JVZHYBL).
They pass the accessibility scan (`pk qa a11y`); see `docs/accessibility/`.
Developer handoff spec: `docs/handoff.md`.

## Start here

This project lives on the `dumpit` branch of `miricoder/project-kit`, with its own history
and no plugin code. In a new session with that repo selected, say:

> check out the dumpit branch and run /project-kit:pipeline

Running the pipeline (it starts with `/design`) accepts the scope in `docs/proposal.md` as written; change the proposal
first if you want a different v1. In yolo mode `/design` hands to `/remediate` (check → fix →
re-check → judge → fix → re-judge until `pk qa` passes), which hands to `/initiate`, which
asks before any development starts.

Judging needs at least one judge API key from a non-Anthropic provider (OpenAI, Gemini, Kimi, …).
Keys are never committed. If the panel is short, the pipeline asks which key you can give; you
store it yourself with `pk keys add <family>` (Project Kit 0.6.0+), or, in a cloud session, as
an environment secret such as `OPENAI_API_KEY`. The other seats can be pasted by hand.
