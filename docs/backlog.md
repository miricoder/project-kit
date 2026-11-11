# Backlog: dumpit

> From docs/spec.md and docs/acceptance.feature, not judged: the judge round was skipped at
> the user's request (judge gate WAIVED, OpenAI judge account had no credit).
> Order is build order. A slice is done when its scenarios pass.

Proposal Phases 0–2 are v1. Phase 0 settles the biggest risk (can a small model file at
≥ 90 %?) before any screen is built, so it comes first.

> **Revised after the platform change (2026-11):** v1 is a web app on the iPhone's Home
> Screen and the computer, with sign-in and the data on the server. Slices 1–2 are unchanged;
> from slice 3 on the backlog is rebuilt around the server store and the web app.

## Slice 1: Op schema, Validator and filing service
- **Delivers:** a running `POST /v1/file` that turns one capture into a validated op list;
  the op schema and Validator rules every later slice relies on
- **Proposal phase:** 0
- **Scenarios:** implausible amount is not filed as an expense
- **Touches:** `service/` (FastAPI): `/v1/install`, `/v1/file`, `/v1/health`, install-token
  hashes, per-install and global limits, one LLM call with schema output and one retry
  (slice 3 turns the install token into the signed-in user and builds the context on the
  server);
  `dumpit_ops` Python package (op schema, 10 categories, Validator rules: refs, date range,
  amount range, ≤ 5 changes, create-only pastes)
- **Done when:** its scenarios pass as automated tests (Validator level, model stubbed);
  `pk qa -C .` still passes

## Slice 2: Filing test set and scorer, first baseline
- **Delivers:** 200 realistic captures with expected ops, a scorer that prints the
  fully-correct share per kind and overall plus cost per capture, and a recorded baseline
- **Proposal phase:** 0
- **Scenarios:** filing test set reports a fully-correct score
- **Touches:** `eval/captures.jsonl`, `eval/score.py`, `eval/report.json`, `dumpit_ops`
  normalisation; at least 50 captures written by someone other than the builder (the spec's
  own strongest counter-argument)
- **Done when:** its scenarios pass as automated tests; baseline score recorded in
  `eval/BASELINE.md`; `pk qa -C .` still passes

## Slice 3: Sign-in and the server store
- **Delivers:** sign-in with an emailed link, per-device sessions, and every item stored on the
  server, filed by the server's Filer
- **Proposal phase:** 1
- **Scenarios:** an old sign-in link does not sign anyone in; a sign-in link is only sent to the user's own
  email; signing out a lost device ends
  its access; data is visible only to the signed-in user; two devices capturing at once never
  lose an item
- **Touches:** Postgres schema 1 and migrations; Auth (`/v1/auth/*`, sessions, one-email
  allowlist, email provider); Captures API (idempotent on `capture_id`, per-user lock); Filer
  and UndoLog writes; the slice-1 filing step moved behind the signed-in user with a server-
  built context snapshot; `/v1/changes`
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes (against a
  test Postgres)

## Slice 4: Web app on the iPhone and the computer
- **Delivers:** the web app you add to your iPhone's Home Screen from Safari and open in a
  browser on your computer: capture bar, log lines, the same data on both
- **Proposal phase:** 1
- **Scenarios:** a typed expense is filed against the month; one sentence becomes two items; an
  expense without a date is filed as today; the monthly budget is set by saying it; dictated
  text is filed like typed text; capture that is not understood is kept as a note; capture over
  4,000 characters is not sent; captures are filed in the order they were said; an item
  captured on the phone shows on the computer; signing in on a new device shows all data; cleared website data comes back on the
  next sign-in
- **Touches:** `web/` (React, TypeScript, Vite): app manifest and icon, service worker (app
  shell), Outbox and Read cache in IndexedDB, sync on open/focus/after filing, Capture screen
  and log from docs/handoff.md; the service serves the built files
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes; checked by
  hand on your iPhone (Add to Home Screen) and a desktop browser

## Slice 5: Safe upgrades
- **Delivers:** database changes that cannot lose data, and a rolled-back service that still
  reads newer data
- **Proposal phase:** 1
- **Scenarios:** failed database upgrade leaves data unchanged; rolled-back service version
  reads data written by the newer version
- **Touches:** numbered migrations run in one transaction before deploy, `schema_meta`,
  additive-only rule, the CI rollback drill
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 6: Reminders
- **Delivers:** a notification at the stated wall-clock time on every device where reminders
  are on, even with the phone locked
- **Proposal phase:** 1
- **Scenarios:** a task with a day and time is filed with a reminder; a reminder fires with the
  phone locked; reminders without notification permission warn the user; an expired push
  subscription is removed and not retried; reminder keeps its wall-clock time after a time zone
  change; ticking a task done cancels its reminder
- **Touches:** Web Push (VAPID keys as secrets), `push_subscription`, permission prompt after
  Add to Home Screen, Reminder sender every minute (Cloud Scheduler), device time zone
  reporting, Dashboard banner
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes (the locked-
  phone one on your iPhone)

## Slice 7: Edit by saying so
- **Delivers:** moving, correcting and cancelling existing items in plain words
- **Proposal phase:** 1
- **Scenarios:** a task is moved by saying so; an amount is corrected by saying so; a task is
  cancelled by saying so; correction applies to the most recent matching expense; correction
  that matches nothing changes nothing; one capture cannot change more than five existing items
- **Touches:** context snapshot refs, `update`/`delete`/`complete_task` in the Filer, item
  revisions, reminder rescheduling
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 8: Undo and redo
- **Delivers:** one-tap undo and redo per item and per capture, with no time limit
- **Proposal phase:** 1
- **Scenarios:** undo restores the previous state in one tap; redo re-applies an undone item;
  undo of a move restores the old due date; undo of an item changed since is refused
- **Touches:** UndoLog (inverse ops, `after_rev` conflict check), `/v1/undo`, `/v1/redo`, log-
  line buttons
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 9: Offline and service failures
- **Delivers:** captures that are never lost: kept on the device offline, retried on errors,
  filed exactly once
- **Proposal phase:** 1
- **Scenarios:** capture sent while offline is filed after reconnecting; relative date in a
  queued capture resolves to the day it was said; app closed mid-filing files the capture
  exactly once; filing service error keeps the words and offers retry; invalid model output is
  never applied; daily filing limit reached keeps captures waiting
- **Touches:** Outbox retry and backoff, `online` events, idempotent resend, waiting and failed
  log rows, Retry
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 10: Dashboard and monthly budget
- **Delivers:** the glanceable Dashboard: due soon, the month, the active trip
- **Proposal phase:** 1
- **Scenarios:** the dashboard shows due tasks, the month and the active trip; month totals by
  category show the top three; month over budget says how much over; a dashboard with nothing
  due says so
- **Touches:** `/v1/dashboard`, Dashboard screen and cards from docs/handoff.md (trip card
  tested with seeded trips until slice 12)
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 11: Phase 1 accuracy bar
- **Delivers:** prompt and model tuned until tasks, expenses and corrections file correctly
- **Proposal phase:** 1
- **Scenarios:** tasks and expenses reach the Phase 1 accuracy bar; twenty test corrections
  meet the Phase 1 bar
- **Touches:** prompt and model version, `eval/` subsets; step up one model tier only if the
  small one stays below 90 %, and record the new per-capture cost
- **Done when:** its scenarios pass against the live model; `pk qa -C .` still passes

## Slice 12: Trips
- **Delivers:** trips from one sentence, backward-scheduled to-dos, trip budget vs spent, and
  expenses linked by name or date
- **Proposal phase:** 2
- **Scenarios:** a trip is created from one sentence with backward-scheduled to-dos; to-dos for
  a trip departing soon are due no later than departure; an expense that names the trip is
  linked to it; an expense during the trip dates is linked by date; expense inside two
  overlapping trips links to the later one; trip spent equals the sum of its linked expenses;
  trip without a budget shows no budget set
- **Touches:** `create_trip`, the to-do template in the Filer, the trip linking rule,
  `/v1/trips/{id}`, Trip screen and trip card
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 13: Pasted notes
- **Delivers:** paste a messy note and get several items, with one Undo all
- **Proposal phase:** 2
- **Scenarios:** a pasted note becomes several items; pasted notes cannot change or delete
  existing items; the paste screen's Send button is disabled while the box is empty; undo all
  reverts every item from a paste
- **Touches:** Pasted notes screen, `source: paste` create-only rule, batch undo
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 14: v1 accuracy bar and 14-day use
- **Delivers:** the end-of-v1 proof: the whole test set at ≥ 90 % and two weeks of real use
- **Proposal phase:** 2
- **Scenarios:** the whole test set reaches the v1 accuracy bar; fewer than one in ten captures
  need a fix during 14 days of use
- **Touches:** `eval/`, a server-side count of undos and corrections per capture (no analytics
  SDK)
- **Done when:** both measured and recorded; `pk qa -C .` still passes
