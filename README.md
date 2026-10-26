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
| design | **next** | `docs/spec.md`, `docs/acceptance.feature` (not written yet) |
| remediate → judge | after design, automatic | `qa/remediation-log.md`, `docs/ruling.md` |
| initiate | after the judges pass it; asks before starting | `docs/backlog.md` |

UI mockups: `ui/*.dc.html` (canvas: https://claude.ai/artifact/YKwgxHfyNuYxb46JVZHYBL).
They pass the accessibility scan (`pk qa a11y`); see `docs/accessibility/`.
Developer handoff spec: `docs/handoff.md`.

## Start here (new Claude Code session with this repo)

```
/project-kit:design
```

Running `/design` accepts the scope in `docs/proposal.md` as written; change the proposal
first if you want a different v1. In yolo mode `/design` hands to `/remediate` (check → fix →
re-check → judge → fix → re-judge until `pk qa` passes), which hands to `/initiate`, which
asks before any development starts.

Judging unattended needs three judge API keys from three non-Anthropic families in
`~/.claude/project-kit/.env`, e.g. `OPENAI_API_KEY`, `GEMINI_API_KEY`, `MOONSHOT_API_KEY`.
