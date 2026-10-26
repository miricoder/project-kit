# Technical spec: Dumpit

> Phase 3 of the Project Kit pipeline. Bound by the v1 cut and out-of-scope list in
> docs/proposal.md (v1 = Phases 0–2). Acceptance criteria live in docs/acceptance.feature.
> UI behaviour, tokens and copy are in docs/handoff.md; this spec does not repeat them.
>
> Assumptions still open from research and proposal, used here as stated: one person, one
> phone, home currency EUR, GDPR applies. Anything marked **ASSUMED** was decided here
> without the user's answer and should be confirmed.

## Architecture

```
 ┌──────────────────────── Android phone (all user data lives here) ───────────────────────┐
 │                                                                                         │
 │  Screens (Dashboard · Capture · Paste · Trip)  ── read ──►  Store (SQLite, versioned)   │
 │        │ text + source                                         ▲         ▲              │
 │        ▼                                                       │ apply   │ schedule     │
 │  CaptureQueue ── durable row first ──► Store.captures          │ (1 txn) │              │
 │        │ oldest pending, one at a time                         │         │              │
 │        ▼                                                       │         │              │
 │  FilingClient ── HTTPS ──┐          Validator ──► Filer ───────┘    Reminders           │
 │        ▲  ops JSON       │              ▲            │              (AlarmManager via   │
 │        └─────────────────┼──────────────┘            └─► UndoLog     local notifications)│
 └──────────────────────────┼──────────────────────────────────────────────────────────────┘
                            ▼
              Filing service (stateless container) ──► LLM API (structured output)
              holds the model key · rate limit · spend cap · no content logged
```

The phone owns every byte of user data and every decision that changes it. The filing
service only turns words into a list of proposed operations; the phone validates them and
applies them deterministically. The model never writes to the store directly.

| Component | Owns | Depends on |
|---|---|---|
| Screens | Rendering the four screens in docs/handoff.md; the capture bar | Store (read), CaptureQueue |
| CaptureQueue | Saving every capture durably *before* any network call; ordering; retry and backoff; offline detection | Store, FilingClient, OS connectivity events |
| FilingClient | One HTTPS call per capture to `POST /v1/file`; builds the context snapshot; install token | Filing service, secure storage |
| Validator | Rejecting any operation that breaks the schema or the safety limits (below) before it reaches the store | Ops schema, Store (to resolve refs) |
| Filer | Applying a validated batch in one SQLite transaction; trip linking; trip to-do generation; writing the inverse operations | Store, UndoLog, Reminders |
| UndoLog | Inverse operations per batch and per item; undo and redo; conflict detection | Store |
| Reminders | Scheduling, cancelling and rescheduling task notifications; exact-alarm permission state; time-zone change handling | OS alarm and notification APIs |
| Store | SQLite database, schema version, migrations, pre-migration backup | Device storage |
| Filing service | Install tokens, per-install rate limit, global daily spend cap, prompt and model version, calling the LLM, schema-checking its output | LLM provider API |
| Eval harness (Phase 0) | The filing test set and the scorer that runs it against the filing service | Filing service, Validator (shared package) |

## Decisions

Each decision names what lost and why. A decision with no rejected alternative was not one.

| Decision | Chosen | Rejected | Why |
|---|---|---|---|
| Phone platform for v1 | **Android** (min API 29, target current) | iOS | Larger share of phones in the EU (the assumed market); €25 one-off store fee vs €99/year; the builder's existing work (exp101) is web/React, not Swift, so neither platform has a native head start. Cost: exact-alarm permission handling (see Failure modes). |
| App framework | **React Native with Expo** (TypeScript), Android build only | Native Kotlin; Flutter | Reuses the React skills shown in exp101/frontend; Expo gives SQLite, secure storage, local notifications and background tasks as maintained modules; keeps iOS reachable later without a rewrite. Kotlin is the better Android fit but is a new language for the builder. |
| Where filing intelligence runs | **Hosted LLM behind a thin service**, structured JSON output | On-device small model; rule-based parser | The proposal's central risk is reaching ≥ 90 % fully-correct filing on mixed sentences and messy pastes; current on-device models and regex parsers are well below that on mixed input (ASSUMED, Phase 0 measures it). The service exists only so the API key is not on the phone. |
| Model | **Smallest current Claude model (Haiku tier)**, one call per capture, temperature 0, tool/JSON-schema output | A larger model by default; several calls per capture (classify then extract) | Per-capture cost target is €0.001–0.01 (proposal). One call with the whole schema keeps cost and latency down. Phase 0 decides: if the small model scores < 90 % after prompt work, step up one tier and record the new per-capture cost. |
| Who applies changes | **The phone, from a validated op list** | Model returns the new full state; server applies | Ops are small, auditable and invertible (undo needs exact inverses). A model returning full state could silently drop items. The server never sees the database, so it cannot be its writer. |
| Trip to-dos | **Deterministic template in the Filer**, offsets from departure | Model generates the to-do list | Proposal criterion 2(a) needs ≥ 5 to-dos, all due before departure, every time. A fixed template is testable and costs nothing; the model only extracts name, dates and budget. |
| Expense ↔ trip link | **Model names the trip if the words do; otherwise a date rule** (expense date within an active trip's dates → that trip) | Model decides every link; date rule only | Words beat dates ("Lisbon hotel deposit" paid in February belongs to the March trip); dates catch the in-trip "coffee 3.50" that names nothing. |
| Categories | **Fixed list of 10**, model picks one, Validator falls back to *Other*: Groceries, Eating out, Transport, Housing, Bills, Health, Shopping, Fun, Travel, Other | Free-text categories invented by the model; the 12-category list in exp101 unchanged | Free text fragments totals ("Food", "Groceries", "Supermarket"). The exp101 list is the starting point but its Savings, Insurance and Education buckets are not spending a person narrates in passing. |
| Local store | **SQLite (expo-sqlite)** with `PRAGMA user_version` and a meta table | AsyncStorage/JSON file (as in exp101/backend/storage/json_storage.py); a sync-ready DB (Realm, WatermelonDB) | Undo and trip totals need transactions and sums; a JSON file rewrites everything on each change and cannot do atomic multi-item batches. Sync is Phase 4, so a sync engine now is weight without use. |
| Money representation | **Integer euro cents** | Floating-point euros | Trip spent total must equal the sum of its expenses exactly (criterion 2(c)). |
| Task times | **Floating local wall-clock time** (date + optional time, no zone), rescheduled on time-zone change | Absolute UTC instants | "Dentist Thursday 3pm" means 3pm wherever the phone is. Travel is a core scenario. |
| Offline capture | **Capture saved locally first, filed later; relative dates resolved against the capture time** | Block sending while offline; resolve at filing time | Proposal: capture works offline. "Tomorrow" said on Monday and filed on Tuesday must still mean Tuesday. |
| Reconnect trigger | **Connectivity listener while the app is alive + Android background task with a network constraint** | Polling; push from the server | The listener meets the 30 s criterion while the app is open or recently backgrounded; the background task covers the rest without a server that knows the device. |
| Filing service host | **One small container (FastAPI, Python) on Google Cloud Run**, scale to zero, one region in the EU | Cloudflare Worker; calling the LLM from the phone | FastAPI is the pattern the builder already runs (exp101/backend/main.py). Scale-to-zero keeps hosting near €0 (proposal: €0–20/month). EU region for GDPR. The phone-direct option leaks the key. |
| Service auth without accounts | **Anonymous per-install token** issued on first launch, kept in Android Keystore-backed secure storage, plus per-token and global limits | No auth; Play Integrity attestation | No auth lets anyone spend the budget. Attestation is the stronger option but adds a Google dependency and setup for a one-user proof; revisit before any public release. |
| Android backup | **Auto Backup off** (`allowBackup=false`) | Android Auto Backup to Google Drive | Proposal: no cloud copy in v1; financial and travel data stays on the phone. The cost (lost phone = lost data) is an accepted proposal risk. |
| Pastes | **Create-only**: a paste may not edit, delete or set the budget | Pastes treated like typed captures | Pasted text is often someone else's words (a forwarded message, a web page). Limiting what it can do caps the damage of a misread or an injected instruction. |
| Undo window | **No time limit; Redo stays until the next capture** (handoff, WCAG 2.2.1) | Snackbar with a 5 s timeout | Mistakes are noticed later, on the dashboard; undo has to still be there. |

**Reused from existing work:** the FastAPI app layout, health endpoint and request middleware
from `miricoder/exp101` `backend/main.py`; the category taxonomy from `exp101`
`frontend/src/utils/categories.js`, cut to 10 (see Decisions). Nothing else in the
repositories that could be opened this session (exp101, tada) does natural-language filing,
reminders or offline queuing, so those parts are new. `one-place` and `travel_ai` were not
inspected (no access this session); if either already has a filing prompt or a trip template,
it should replace the matching part here.

## Data model

All user data lives in one SQLite file in the app's private storage on the phone. The filing
service stores no user data.

| Entity | Fields | Lives in |
|---|---|---|
| `capture` | `id` (UUID v4), `text` (≤ 4,000 chars), `source` (typed · paste), `captured_at` (local datetime + IANA zone), `status` (pending · filing · filed · failed · note), `attempts`, `last_error`, `filed_batch_id?` | Phone SQLite |
| `batch` | `id`, `capture_id` (unique), `applied_at`, `prompt_version`, `model`, `undone_at?` | Phone SQLite |
| `undo_entry` | `id`, `batch_id`, `item_kind`, `item_id`, `inverse_op` (JSON), `after_rev` (item revision the op produced) | Phone SQLite |
| `task` | `id`, `ref` (short id shown to the model), `title`, `due_date?`, `due_time?`, `done_at?`, `trip_id?`, `template_key?`, `rev`, `deleted_at?`, `created_batch_id` | Phone SQLite |
| `expense` | `id`, `ref`, `amount_cents` (int, > 0), `date`, `category` (one of 10), `description`, `trip_id?`, `trip_link` (named · by_date · none), `rev`, `deleted_at?`, `created_batch_id` | Phone SQLite |
| `trip` | `id`, `ref`, `name`, `start_date`, `end_date`, `budget_cents?`, `rev`, `deleted_at?`, `created_batch_id` | Phone SQLite |
| `note` | `id`, `capture_id`, `text`, `suggestions` (JSON, ≤ 3) | Phone SQLite |
| `setting` | `key`, `value` — `monthly_budget_cents`, `home_currency` (EUR), `install_token_set` | Phone SQLite |
| `schema_meta` | `schema_version`, `min_reader_version`, `migrated_at` | Phone SQLite |
| install token | opaque 256-bit token | Phone secure storage (Keystore); server keeps only its SHA-256 and a daily counter |

Relationships: `expense.trip_id → trip`, `task.trip_id → trip` (trip to-dos are tasks with a
`template_key`), `batch.capture_id → capture`, `undo_entry.batch_id → batch`. Deletes are soft
(`deleted_at`) so undo can restore them; rows soft-deleted more than 90 days ago are purged on
app start. A task's `ref`, an expense's `ref` and a trip's `ref` are short, non-reused codes
(`t12`, `e88`, `p3`) so the model can point at items without seeing database ids.

**Derived figures (never stored):** month spent = sum of non-deleted expenses dated in the
calendar month; trip spent = sum of non-deleted expenses with that `trip_id`; left = budget −
spent. Trip expenses count in both.

- **Schema versioning:** `PRAGMA user_version` holds `schema_version`; `schema_meta` also
  holds `min_reader_version`, the oldest app schema that can still read and write this file
  safely. v1 ships at schema 1.
- **Migration:** forward migrations are numbered SQL files run in one transaction at app start.
  Before running any, the app copies the database file to `dumpit.v<old>.bak` (keeps the last
  two). In v1, migrations are **additive only** (new tables, new nullable columns, new
  indexes), so `min_reader_version` stays 1 and an older app keeps working on newer data.
  **Reverse:** no down-migrations are run on the phone. An older build that finds
  `schema_version` above its own but `min_reader_version` ≤ its own opens the file normally
  and ignores unknown columns; if `min_reader_version` is above its own it restores the newest
  `.bak` that it can read, after telling the user what that loses (captures since the upgrade).
  A non-additive change (dropping or retyping a column) is not allowed in v1.

## Interfaces

**Filing service (HTTPS, JSON, EU region).** All requests carry `Authorization: Bearer
<install token>` except `/v1/install`.

```
POST /v1/install                      → 201 {install_token}
POST /v1/file
  {capture_id, text, source: "typed"|"paste", captured_at: "2026-02-23T09:14:00",
   tz: "Europe/Lisbon", currency: "EUR",
   context: {
     tasks:    [{ref, title, due_date?, due_time?, done}]          // ≤ 50 open + 10 latest done
     expenses: [{ref, amount_cents, date, category, description, trip_ref?}]  // last 30 days, ≤ 100
     trips:    [{ref, name, start_date, end_date, budget_cents?}]  // not ended > 30 days ago
     monthly_budget_cents?
   }}
  → 200 {capture_id, prompt_version, model, ops: [Op], usage: {input_tokens, output_tokens}}
  → 400 malformed request · 401 unknown token · 413 text > 4,000 chars
  → 429 per-install limit (200 captures/day) with Retry-After
  → 502 model output failed schema check twice · 503 provider down or global daily spend cap hit
GET  /v1/health                       → 200 {status, prompt_version, model}
```

**Op schema** (the only things the model can propose):

```
create_task        {title, due_date?, due_time?}
create_expense     {amount_cents, date, category, description, trip_ref?}
create_trip        {name, start_date, end_date, budget_cents?}
update             {ref, set: {field: value}}        // fields allowed per kind, as in create_*
delete             {ref}
complete_task      {ref}
set_monthly_budget {amount_cents}
note               {text, suggestions: [{label, op}]}  // ≤ 3 suggested ops, never applied unasked
```

**Validator rules** (phone, shared package also used by the eval harness): every `ref` exists
and is not deleted; dates are real calendar dates between 2 years ago and 5 years ahead;
`amount_cents` is 1 … 10,000,000 (€0.01 – €100,000); `category` is one of the 10; trip
`end_date ≥ start_date`; at most **5** `update`/`delete`/`complete_task` ops per capture; a
`paste` capture may contain only `create_*` and `note` ops. A batch with any invalid op is
rejected whole and the capture becomes a note (never partially applied).

**Phone modules** (TypeScript):

```
CaptureQueue.enqueue(text, source): CaptureId          // writes row, returns at once
CaptureQueue.drain(): Promise<void>                     // files pending captures oldest-first, one at a time
Filer.apply(captureId, ops): BatchResult                // one transaction; idempotent on captureId
UndoLog.undo(batchId | itemId): UndoResult              // "undone" | "conflict"
UndoLog.redo(batchId | itemId): UndoResult
Reminders.sync(taskIds?): void                          // (re)schedule from the store
Store.dashboard(today): {dueSoon, month, activeTrips}
Store.trip(tripId): {trip, todos, expenses, spentCents}
```

**Trip to-do template** (offsets from `start_date`; any date before today is clamped to today):
book travel −42 d, book stay −35 d, check passport/ID −28 d, pay remaining balances −7 d,
pack −1 d.

**Eval harness (Phase 0):** `eval/captures.jsonl`, one case per line —
`{id, today, tz, context, text, source, expected_ops}`; `python -m eval.score --service URL`
prints per-kind and overall *fully correct* share (kind, amount, date, category, trip link all
equal after Validator normalisation), mean cost per capture, and writes `eval/report.json`.

## Failure modes

| What goes wrong | System does | Scenario |
|---|---|---|
| No connection when a capture is sent | Capture saved as pending, shown as "Waiting to file"; filed automatically on reconnect | capture sent while offline is filed after reconnecting |
| A relative date is said offline and filed the next day | Dates resolve against `captured_at`, not the filing time | relative date in a queued capture resolves to the day it was said |
| App killed or phone dies while a capture is filing | Capture stays pending; on next start it is filed again; `Filer.apply` is idempotent on `capture_id`, so nothing is filed twice | app closed mid-filing files the capture exactly once |
| Several captures sent quickly, or queued offline | Filed strictly oldest-first, one at a time, so an edit always sees the item it edits | captures are filed in the order they were said |
| Filing service or model provider returns an error | Two automatic retries (5 s, 30 s); then the capture shows "Couldn't file this. Your words are saved" with Retry | filing service error keeps the words and offers retry |
| Per-install daily limit or global spend cap reached | Captures stay pending with the reason shown; filed when the limit resets | daily filing limit reached keeps captures waiting |
| Model output breaks the op schema | Service retries the model once; a second failure returns 502 and the phone treats it as a service error | invalid model output is never applied |
| Model output is valid JSON but breaks a Validator rule (unknown ref, impossible date, amount out of range) | Whole batch rejected; capture kept as a note with suggestions; nothing applied | implausible amount is not filed as an expense |
| Capture is not understood | Kept as a note; up to 3 one-tap suggestions; nothing else changes | capture that is not understood is kept as a note |
| A correction matches no item | Nothing changes; the log says what it looked for | correction that matches nothing changes nothing |
| A correction matches several items | The most recent matching item changes; the log line names it, with Undo | correction applies to the most recent matching expense |
| Pasted text contains edits, deletions or instructions | Paste is create-only; any update/delete op rejects the batch to a note | pasted notes cannot change or delete existing items |
| One capture tries to change many existing items | More than 5 update/delete/complete ops rejects the batch to a note | one capture cannot change more than five existing items |
| Undo of an item that a later capture changed | Undo refused for that item with "changed since — say the correction instead"; other items in the batch undo normally | undo of an item changed since is refused |
| Exact-alarm permission not granted (Android 12+) | Reminders still scheduled inexactly; a banner on the Dashboard explains and links to the setting | reminders without exact alarm permission warn the user |
| Phone changes time zone (travel) | All future reminders rescheduled to the same wall-clock time in the new zone | reminder keeps its wall-clock time after a time zone change |
| Paste or typed text over 4,000 characters | Send disabled; the text stays in the box with a count and a message | capture over 4,000 characters is not sent |
| Trip departs sooner than the template offsets | To-dos that would be in the past are due today; none is after departure | to-dos for a trip departing soon are due no later than departure |
| Expense falls inside two overlapping trips and names neither | Linked to the trip with the later start date; the log line names the trip, with Undo | expense inside two overlapping trips links to the later one |
| Month spending passes the budget | Bar turns warn colour; "€X over" replaces "left" | month over budget says how much over |
| Database upgrade fails on app update | Migration transaction rolls back; the `.bak` is untouched; app shows an error and keeps the old schema working | failed database upgrade leaves data unchanged |
| A rolled-back (older) app build opens data written by a newer build | Opens normally because v1 migrations are additive and `min_reader_version` is 1 | rolled-back app version opens data written by the newer version |

## Rollback

| Layer | How | Tested by |
|---|---|---|
| Code | **App:** Play does not allow downgrades, so a bad release is rolled back by rebuilding the previous git tag with a higher `versionCode` and releasing it (staged rollout at 20 % first so a bad build can be halted). **Filing service:** redeploy the previous container image tag on Cloud Run (traffic switch, under a minute); prompt and model are pinned in that image, so the previous filing behaviour comes back with it. | CI rollback drill: build tag N and tag N−1-as-higher-versionCode, install N on an emulator, add data, install the rebuild, run the smoke scenarios. Service: deploy N, then N−1, call `/v1/health` and the 20-case eval smoke set. |
| Data | **Phone:** no down-migrations. v1 migrations are additive only, so the rolled-back build reads newer data (`min_reader_version`); a failed upgrade rolls back its own transaction; the last two pre-migration `.bak` copies are kept for the case where a future non-additive change has to be reversed. **Service:** holds no user data; nothing to roll back beyond install-token hashes, which are append-only. **User-level:** undo/redo per capture. | Scenarios "failed database upgrade leaves data unchanged" and "rolled-back app version opens data written by the newer version", run in the same CI drill. |

## Security and privacy

| Concern | Handling |
|---|---|
| Sensitive data | Spending, appointments and travel dates/places. Stored only on the phone in app-private storage, covered by Android file-based encryption; Auto Backup off. Each capture's text plus a context snapshot (titles, amounts, dates of recent items) is sent over TLS to the filing service and the LLM provider for that one request. Neither the service nor the provider (commercial API terms: no training on API data) keeps it beyond the request, except the provider's own abuse-monitoring retention, which the privacy notice states. |
| Secrets | LLM API key: Cloud Run secret (Secret Manager), never in the app or the repo. Install token: Keystore-backed secure storage on the phone; server stores only `sha256(token)`. No other secrets in v1. |
| What gets logged | Service: request id, install-token hash prefix (8 chars), status code, latency, token counts, op kinds and counts, prompt version. **Never** capture text, context, amounts or model output. Phone: no analytics SDK; crash reports off by default in v1. |
| Abuse and cost | Per-install 200 captures/day; 4,000-char input cap; global daily spend cap (default €2/day) after which the service returns 503. |
| Prompt injection | The model can only propose ops on the user's own data; the Validator enforces the op schema, ref existence, amount/date ranges, the 5-change limit and create-only pastes. Worst case is a wrong but visible filing with Undo. |
| GDPR | Single user is also the data subject; data minimised to what filing needs; EU-region service; privacy notice names the LLM provider as processor. Deleting the app deletes all data. |

## Not built

Carried from the proposal so no reader assumes it was covered: day-by-day itinerary
generation; bank or card connection; receipt photos and image/file drop (paste of text only);
calendar integration (edits change the app's own tasks only); accounts, cloud sync, backup or a
second device; sharing, shared trips and split costs; multiple currencies (EUR only, no
conversion); iOS, tablet and web (Android phone only); home-screen widget, watch app and daily
summary push; recurring items and per-category budgets; any assistant that books, buys, emails
or calls; chat or free-form questions about the data. Also not built in v1, decided here: dark
mode (tokens allow it later), Play Integrity attestation, crash reporting, a custom voice
recorder (the keyboard's dictation is used).

## Strongest counter-argument

**The design moves the hard problem into a place it cannot be tested before users arrive.**
Everything deterministic here (queue, undo, totals, reminders, migrations) is well understood
and will work. The product, though, lives or dies on one number, the fully-correct filing rate
on real people's words, and this design measures it only against a test set the builder writes
themselves (Phase 0). Self-written captures are cleaner, shorter and more like the prompt than
what people actually say ("the thing with Marta's present, 30ish, put it on the card"). A small
model that scores 92 % on the builder's 200 cases can plausibly score 75–80 % on a stranger's
fortnight, and at that rate the one-line confirmation is no longer a glance but a review of
every capture, which is exactly the burden the product promises to remove. The design then has
no cheap lever: a bigger model breaks the cost envelope, extra clarifying questions break the
"no forms" rule, and the context snapshot (≤ 50 tasks, 30 days of expenses) means corrections to
older items silently fail to match.

Three further weak points a judge should press. (1) **Android background limits:** the 30 s
reconnect promise holds while the app is alive; if the OS has killed it, filing waits for the
next background task window (often 15 minutes or more) or the next app open, and
manufacturer battery savers (Samsung, Xiaomi) can delay reminders too. (2) **Single device, no
backup:** for an app whose pitch is "trust it with everything", a dropped phone erasing a
month of spending and a booked trip's to-dos may lose the one tester the 14-day criterion
needs. (3) **The proposal's own recommended concierge test has not been run**; building the
filing service before knowing whether people narrate mixed life admin at all risks a
well-engineered answer to a question nobody asked.

If the judges accept only one change, the strongest is: make Phase 0's test set include at
least 50 captures written by people other than the builder, and gate Phase 1 on that subset's
score, not the whole set's.
