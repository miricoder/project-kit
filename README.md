# Dumpit

Tell it your life admin in passing — "paid 42 for groceries", "move the dentist to Friday",
"Lisbon for a long weekend in March, about 600 all in" — and it files tasks, spending and
trips for you, with a dashboard you can glance at.
A web app you add to your iPhone's Home Screen and also open on your computer, with the same
data on both (sign-in with an emailed link; data stored in the EU).

Planned with [Project Kit](https://github.com/miricoder/project-kit). Mode: `yolo`.

## Where things stand

| Phase | Status | File |
|---|---|---|
| ideate | complete | `docs/research.md` |
| proposal | complete | `docs/proposal.md` |
| design | complete; **revised after initiate** for the web app and sign-in with sync | `docs/spec.md`, `docs/acceptance.feature` |
| remediate → judge | lint and a11y pass; **judge round skipped by the user** (gate `WAIVED`: OpenAI judge account has no credit), so the plan is unjudged | `qa/remediation-log.md` |
| initiate | complete: 14 slices, all 60 scenarios covered (rebuilt after the platform change) | `docs/backlog.md` |
| build | slices 1, 3 and 4 done: filing service, sign-in with the server store (Postgres), and the web app for iPhone and computer; slice 2 blocked on `ANTHROPIC_API_KEY` and 50 captures by others (`eval/BASELINE.md`); slices 5–14 to go (`pk slice list`) | `dumpit_ops/`, `service/`, `web/`, `eval/`, `tests/` |

UI mockups: `ui/*.dc.html` (canvas: https://claude.ai/artifact/YKwgxHfyNuYxb46JVZHYBL).
They pass the accessibility scan (`pk qa a11y`); see `docs/accessibility/`.
Developer handoff spec: `docs/handoff.md`.

## Run it

You need Python 3.11+, Node 22 and Postgres 14+.

```bash
pip install -r requirements-dev.txt
(cd web && npm ci && npm run build)

export DUMPIT_DATABASE_URL=postgresql://localhost/dumpit   # an empty database; migrated on start
export DUMPIT_ALLOWED_EMAIL=you@example.com                 # the one email that may sign in
export ANTHROPIC_API_KEY=...                                # the real filer (Claude Haiku 5.5)
uvicorn service.server:app --port 8080
```

Open http://localhost:8080, ask for a sign-in link, and open it. Without an email provider
the link is only logged; set `DUMPIT_SMTP_URL` (for example
`smtps://user:password@smtp.example.com:465`) and `DUMPIT_MAIL_FROM` to email it, or
`DUMPIT_DEV=1` to get a "Dev: open the sign-in link" button on a local machine. Without an
API key, `DUMPIT_MODEL=demo` files a few simple sentence shapes so you can try the app; it
labels itself as the demo filer.

**On your iPhone:** open the app's https address in Safari → Share → Add to Home Screen.
**Tests:** `sh scripts/test.sh` (Python against a throwaway Postgres, the web app's unit
tests, and the browser tests). **Deploy:** `sh scripts/setup-secrets.sh staging`, then
`sh scripts/deploy.sh staging` (Cloud Run, EU). The whole path from here to a launched app,
including the review and the gates, is in [docs/deploying.md](docs/deploying.md).

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
