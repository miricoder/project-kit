# Backlog: dumpit

> From docs/spec.md and docs/acceptance.feature, not judged: the judge round was skipped at
> the user's request (judge gate WAIVED, OpenAI judge account had no credit).
> Order is build order. A slice is done when its scenarios pass.

Proposal Phases 0–2 are v1. Phase 0 settles the biggest risk (can a small model file at
≥ 90 %?) before any phone screen is built, so it comes first.

## Slice 1: Op schema, Validator and filing service
- **Delivers:** a running `POST /v1/file` that turns one capture into a validated op list;
  the op schema and Validator rules every later slice relies on
- **Proposal phase:** 0
- **Scenarios:** implausible amount is not filed as an expense
- **Touches:** `service/` (FastAPI): `/v1/install`, `/v1/file`, `/v1/health`, install-token
  hashes, per-install and global limits, one LLM call with schema output and one retry;
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

## Slice 3: Phone store, capture queue and Filer
- **Delivers:** the Expo/React Native Android app with a capture bar that files tasks,
  expenses and the monthly budget, one capture at a time, with a log line per item
- **Proposal phase:** 1
- **Scenarios:** a typed expense is filed against the month; one sentence becomes two items;
  an expense without a date is filed as today; the monthly budget is set by saying it;
  dictated text is filed like typed text; capture that is not understood is kept as a note;
  capture over 4,000 characters is not sent; captures are filed in the order they were said
- **Touches:** `app/`: Store (SQLite schema 1, integer cents), CaptureQueue, FilingClient,
  Validator (TypeScript port of `dumpit_ops`, sharing its JSON test vectors), Filer, capture
  log; Capture screen from docs/handoff.md
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 4: Schema versioning and safe upgrades
- **Delivers:** migrations that cannot lose data, and a rolled-back build that still opens
  newer data
- **Proposal phase:** 1
- **Scenarios:** failed database upgrade leaves data unchanged; rolled-back app version opens
  data written by the newer version
- **Touches:** Store migrations, `schema_meta`, `min_reader_version`, `.bak` copies
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 5: Reminders
- **Delivers:** task notifications at the stated wall-clock time, even with the phone locked
- **Proposal phase:** 1
- **Scenarios:** a task with a day and time is filed with a reminder; a reminder fires with the
  phone locked; reminders without exact alarm permission warn the user; reminder keeps its
  wall-clock time after a time zone change; ticking a task done cancels its reminder
- **Touches:** Reminders (expo-notifications, exact-alarm permission state, time-zone change
  handler), Dashboard banner
- **Done when:** its scenarios pass as automated tests (the locked-phone one on an emulator);
  `pk qa -C .` still passes

## Slice 6: Edit by saying so
- **Delivers:** moving, correcting and cancelling existing items in plain words
- **Proposal phase:** 1
- **Scenarios:** a task is moved by saying so; an amount is corrected by saying so; a task is
  cancelled by saying so; correction applies to the most recent matching expense; correction
  that matches nothing changes nothing; one capture cannot change more than five existing items
- **Touches:** FilingClient context snapshot (refs), `update`/`delete`/`complete_task` ops in
  Filer, item revisions, Reminders.sync
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 7: Undo and redo
- **Delivers:** one-tap undo and redo per item and per capture, with no time limit
- **Proposal phase:** 1
- **Scenarios:** undo restores the previous state in one tap; redo re-applies an undone item;
  undo of a move restores the old due date; undo of an item changed since is refused
- **Touches:** UndoLog (inverse ops, `after_rev` conflict check), capture log buttons
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 8: Offline and service failures
- **Delivers:** captures that are never lost: queued offline, retried on errors, filed once
- **Proposal phase:** 1
- **Scenarios:** capture sent while offline is filed after reconnecting; relative date in a
  queued capture resolves to the day it was said; app closed mid-filing files the capture
  exactly once; filing service error keeps the words and offers retry; invalid model output is
  never applied; daily filing limit reached keeps captures waiting
- **Touches:** CaptureQueue retry/backoff, connectivity listener, background task, Filer
  idempotency on `capture_id`, waiting and failed log rows
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 9: Dashboard and monthly budget
- **Delivers:** the glanceable Dashboard: due soon, the month, the active trip
- **Proposal phase:** 1
- **Scenarios:** the dashboard shows due tasks, the month and the active trip; month totals by
  category show the top three; month over budget says how much over; a dashboard with nothing
  due says so
- **Touches:** `Store.dashboard(today)`, Dashboard screen and cards from docs/handoff.md
  (trip card renders once Slice 11 creates trips; tested with seeded trips here)
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 10: Phase 1 accuracy bar
- **Delivers:** prompt and model tuned until tasks, expenses and corrections file correctly
- **Proposal phase:** 1
- **Scenarios:** tasks and expenses reach the Phase 1 accuracy bar; twenty test corrections
  meet the Phase 1 bar
- **Touches:** service prompt and model version, `eval/` subsets; step up one model tier only
  if the small one stays below 90 %, and record the new per-capture cost
- **Done when:** its scenarios pass against the live service; `pk qa -C .` still passes

## Slice 11: Trips
- **Delivers:** trips from one sentence, backward-scheduled to-dos, trip budget vs spent, and
  expenses linked by name or date
- **Proposal phase:** 2
- **Scenarios:** a trip is created from one sentence with backward-scheduled to-dos; to-dos for
  a trip departing soon are due no later than departure; an expense that names the trip is
  linked to it; an expense during the trip dates is linked by date; expense inside two
  overlapping trips links to the later one; trip spent equals the sum of its linked expenses;
  trip without a budget shows no budget set
- **Touches:** `create_trip` op, trip to-do template in Filer, trip linking rule,
  `Store.trip(tripId)`, Trip screen and trip card
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 12: Pasted notes
- **Delivers:** paste a messy note and get several items, with one Undo all
- **Proposal phase:** 2
- **Scenarios:** a pasted note becomes several items; pasted notes cannot change or delete
  existing items; the paste button is disabled with an empty clipboard; undo all reverts every
  item from a paste
- **Touches:** Paste screen, clipboard state, `source: paste` create-only rule, batch undo
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 13: v1 accuracy bar and 14-day use
- **Delivers:** the end-of-v1 proof: the whole test set at ≥ 90 % and two weeks of real use
- **Proposal phase:** 2
- **Scenarios:** the whole test set reaches the v1 accuracy bar; fewer than one in ten captures
  need a fix during 14 days of use
- **Touches:** `eval/`, a local undo/correction counter (no analytics SDK), release build
- **Done when:** both measured and recorded; `pk qa -C .` still passes
