# Technical spec: Dumpit

> Phase 3 of the Project Kit pipeline. Bound by the v1 cut and out-of-scope list in
> docs/proposal.md (v1 = Phases 0–2). Acceptance criteria live in docs/acceptance.feature.
> UI behaviour, tokens and copy are in docs/handoff.md; this spec does not repeat them.
>
> **Revised after /initiate at the user's request (2026-11):** v1 is a web app installed to
> the iPhone's Home Screen and opened in a browser on the computer, with the same data on
> every device through a sign-in and a cloud database. This replaces the earlier
> phone-only design (Android, then native iPhone), where all data stayed on one phone.
>
> Assumptions still open, used here as stated: one person, home currency EUR, GDPR applies.
> Anything marked **ASSUMED** was decided here without the user's answer and should be
> confirmed.

## Architecture

```
 ┌── iPhone: Home Screen web app ──┐   ┌── Computer: same web app in a browser ──┐
 │ Screens · capture bar           │   │ Screens · capture bar                   │
 │ Outbox (IndexedDB): captures    │   │ Outbox (IndexedDB)                      │
 │   saved here first              │   │ Read cache (last synced items)          │
 │ Read cache · service worker     │   └──────────────────┬──────────────────────┘
 └───────────────┬─────────────────┘                      │
                 │ HTTPS, session cookie                   │
                 ▼                                         ▼
 ┌────────────────────────── Dumpit service (Cloud Run, EU) ────────────────────────────┐
 │ Auth (email sign-in link) · Captures API · Items API · Undo · Sync (changes since)  │
 │ Filer: Validator → apply ops in one DB transaction → UndoLog                         │
 │ Filing step: one model call per capture (op list)  ──────►  LLM API (Claude Haiku)   │
 │ Reminder sender (every minute) ──► Web Push (Apple / browser push services)          │
 │ Serves the web app's static files                                                     │
 └───────────────────────────────────────┬──────────────────────────────────────────────┘
                                         ▼
                        Postgres (managed, EU region): all user data
```

The server is now the home of the data. Every device holds an outbox of unsent captures
and a read cache of the last synced items, so capture works offline and the dashboard opens
instantly; the server applies every change. The model still only proposes ops; the
Validator and Filer, both on the server, decide what is applied.

| Component | Owns | Depends on |
|---|---|---|
| Web app (React, TypeScript, PWA) | The screens in docs/handoff.md, the capture bar, install-to-Home-Screen, notification permission | Service API, browser storage |
| Outbox | Saving each capture on the device *before* any network call; sending oldest-first, one at a time; retry and backoff; offline detection | IndexedDB, `online` events |
| Read cache | The last synced items per device; showing them offline; pulling changes since the last sync | IndexedDB, Sync API |
| Service worker | Caching the app shell so it opens offline; receiving Web Push and showing the notification | Browser |
| Auth | Email sign-in links, sessions (cookie), signing out a device | Email provider, Postgres |
| Captures API | Accepting a capture, idempotent on `capture_id`; running filing; returning the log lines | Filing step, Filer |
| Filing step | Building the context snapshot from the user's items; one model call; schema check and one retry; limits and spend cap | LLM API (code from slice 1) |
| Validator | Rejecting any op that breaks the schema or the safety limits | Ops schema (`dumpit_ops`) |
| Filer | Applying a validated batch in one transaction; trip linking; trip to-do template; writing inverse ops | Postgres, UndoLog |
| UndoLog | Inverse ops per batch and per item; undo and redo; conflict detection | Postgres |
| Reminder sender | Every minute, sending a Web Push for each task due now in the user's current time zone | Postgres, Web Push services |
| Postgres | Users, sessions, items, captures, batches, undo entries, push subscriptions; schema version and migrations | Managed provider |
| Eval harness (Phase 0) | The filing test set and the scorer | Filing step, Validator |

## Decisions

Each decision names what lost and why. A decision with no rejected alternative was not one.

| Decision | Chosen | Rejected | Why |
|---|---|---|---|
| How v1 reaches the user's devices | **One web app**: installed on the iPhone from Safari (Share → Add to Home Screen, iOS 16.4+), opened in any browser on the computer; Android phones can install it the same way | Native iPhone app; native Android app | The user wants an app icon on their iPhone without the Apple Developer Program or Xcode, and the same app on their computer. A Home Screen web app needs neither and has no 7-day expiry. Cost: less background time than a native app (see Failure modes), and Web Push instead of local notifications. |
| Where the data lives | **Server (managed Postgres, EU region)**, with an outbox and read cache on each device | Data only on the phone (previous design) | The user wants the same data on phone and computer in v1 (decided after /initiate). A server copy also means a lost phone loses nothing. Cost: user data now leaves the phone, so the privacy section changes. |
| Web app framework | **React + TypeScript (Vite), PWA**, with the native path left open through Capacitor later | Expo / React Native Web | The builder's existing work (exp101) is React. Service worker, Web Push and IndexedDB are first-class on the web and awkward through React Native Web. Capacitor can later wrap the same code as an App Store app if the user joins the Apple program. |
| Database provider | **Managed Postgres, EU region, free tier (Neon proposed, ASSUMED)** | Cloud SQL; Firestore; Supabase | Postgres gives transactions and exact sums (undo, trip totals). Cloud SQL costs ~€10/month even when idle; Firestore lacks multi-row SQL transactions and sums; Supabase free projects pause after a week idle. |
| Sign-in | **Email sign-in link** (one-time link, 15-minute expiry), then a session cookie kept 90 days per device | Passwords; passkeys; Apple/Google sign-in | No password to remember or leak; works the same on iPhone and any computer. Passkeys are stronger but cross-device setup on a non-Apple computer is fiddly; revisit later. Needs a transactional email provider (Postmark or Resend, ASSUMED). |
| Where filing intelligence runs | **Hosted LLM behind the service**, structured JSON output | On-device model; rule-based parser | Reaching ≥ 90 % fully-correct filing on mixed sentences is the proposal's central risk; small local models and regex parsers are well below that (ASSUMED, Phase 0 measures it). |
| Model | **Claude Haiku 5.5** (`claude-haiku-5-5`, ~$0.10 / $0.50 per million input / output tokens), one call per capture, structured JSON output | A larger model by default; several calls per capture | Per-capture cost target is €0.001–0.01 (proposal). Phase 0 decides: below 90 % after prompt work, step up one tier and record the new cost. The API no longer accepts sampling parameters, so there is no temperature setting. |
| Who applies changes | **The server's Filer, from a validated op list, in one transaction** | The model returns new full state; each device applies | Ops are small, auditable and invertible. With data on the server, applying there keeps every device consistent. |
| Trip to-dos | **Deterministic template in the Filer**, offsets from departure | Model generates the list | Criterion 2(a) needs ≥ 5 to-dos all due before departure, every time; a template is testable and free. |
| Expense ↔ trip link | **Model names the trip if the words do; otherwise a date rule** | Model decides every link; date rule only | Words beat dates ("Lisbon hotel deposit" paid in February); dates catch the in-trip "coffee 3.50". |
| Categories | **Fixed list of 10**, Validator falls back to *Other*: Groceries, Eating out, Transport, Housing, Bills, Health, Shopping, Fun, Travel, Other | Free-text categories; exp101's 12 unchanged | Free text fragments totals. |
| Money | **Integer euro cents** | Floating-point euros | Trip spent must equal the sum of its expenses exactly (criterion 2(c)). |
| Task times | **Floating local wall-clock time** (date + optional time, no zone); the server sends the reminder at that time in the user's current time zone, which each device reports when opened | Absolute UTC instants | "Dentist Thursday 3pm" means 3pm wherever the user is. |
| Offline capture | **Saved in the device outbox first, sent later; relative dates resolved against the capture time** | Block sending offline; resolve at filing time | "Tomorrow" said on Monday and filed on Tuesday must still mean Tuesday. |
| Reminders | **Web Push from the server** (VAPID), per-device subscription | Local notifications (not available to web apps) | The only way a web app can notify with the phone locked. Cost: reminder titles and times are on the server, which they now are anyway. |
| Sync | **Pull "changes since" on open, on focus, after each filing and every 30 s while visible**; the server is the single writer | Live push of changes (WebSocket); multi-writer merge on devices | One person, few devices: polling on focus is enough to make the computer match the phone within seconds of looking, and a single writer means no merge conflicts. |
| Hosting | **One Cloud Run service (FastAPI), EU region, scale to zero**, serving the API and the web app's static files from one origin | Separate static host; Cloudflare Workers | One origin means a simple session cookie and no cross-origin setup; scale to zero keeps cost near €0. FastAPI is the pattern the builder already runs. |
| Pastes | **Create-only**: a paste may not edit, delete or set the budget | Pastes treated like typed captures | Pasted text is often someone else's words. |
| Undo window | **No time limit; Redo stays until the next capture** | Snackbar with a 5 s timeout | Mistakes are noticed later, on the dashboard. |

**Reused from existing work:** slice 1 (`dumpit_ops` op schema and Validator; the service's
model call, limits, spend cap and logging rules) carries over: the per-install token becomes
the signed-in user, and the phone-supplied context snapshot is now built on the server. The
FastAPI layout comes from `miricoder/exp101` `backend/main.py`; the category list from
`exp101` `frontend/src/utils/categories.js`, cut to 10.

## Data model

All user data lives in Postgres on the server. Each device keeps only its outbox and a read
cache, both in IndexedDB.

| Entity | Fields | Lives in |
|---|---|---|
| `user` | `id`, `email` (unique), `tz` (IANA, last reported), `monthly_budget_cents?`, `home_currency` (EUR), `created_at` | Postgres |
| `sign_in_link` | `token_hash`, `user_email`, `expires_at`, `used_at?` | Postgres |
| `session` | `id`, `user_id`, `token_hash`, `device_label`, `created_at`, `last_seen_at`, `revoked_at?` | Postgres |
| `push_subscription` | `id`, `user_id`, `session_id`, `endpoint`, `keys` (p256dh, auth), `created_at` | Postgres |
| `capture` | `id` (UUID v4 from the device), `user_id`, `text` (≤ 4,000 chars), `source` (typed · paste), `captured_at` (local datetime + IANA zone), `status` (filed · failed · note), `filed_batch_id?` | Postgres |
| `batch` | `id`, `capture_id` (unique), `applied_at`, `prompt_version`, `model`, `undone_at?` | Postgres |
| `undo_entry` | `id`, `batch_id`, `item_kind`, `item_id`, `inverse_op` (JSON), `after_rev` | Postgres |
| `task` | `id`, `user_id`, `ref`, `title`, `due_date?`, `due_time?`, `done_at?`, `trip_id?`, `template_key?`, `reminded_at?`, `rev`, `deleted_at?`, `created_batch_id`, `updated_seq` | Postgres |
| `expense` | `id`, `user_id`, `ref`, `amount_cents` (int, > 0), `date`, `category`, `description`, `trip_id?`, `trip_link` (named · by_date · none), `rev`, `deleted_at?`, `created_batch_id`, `updated_seq` | Postgres |
| `trip` | `id`, `user_id`, `ref`, `name`, `start_date`, `end_date`, `budget_cents?`, `rev`, `deleted_at?`, `created_batch_id`, `updated_seq` | Postgres |
| `note` | `id`, `user_id`, `capture_id`, `text`, `suggestions` (JSON, ≤ 3), `updated_seq` | Postgres |
| `schema_meta` | `schema_version`, `migrated_at` | Postgres |
| outbox entry | `capture_id`, `text`, `source`, `captured_at`, `tz`, `state` (waiting · sending · failed), `last_error` | Device IndexedDB |
| read cache | the user's items as of `last_seq`, plus `last_seq` | Device IndexedDB |

Every user row carries `user_id`; every query is scoped by it. `updated_seq` comes from one
per-user counter bumped on each change, so a device asks for "everything with
`updated_seq` > my `last_seq`" (deletes included, as soft-deleted rows). Deletes are soft so
undo can restore them; rows soft-deleted over 90 days ago are purged nightly. Refs (`t12`,
`e88`, `p3`) are per user, short and never reused.

**Derived figures (never stored):** month spent = sum of non-deleted expenses dated in the
calendar month; trip spent = sum of non-deleted expenses with that `trip_id`; left = budget −
spent. Trip expenses count in both.

- **Schema versioning:** `schema_meta.schema_version`, starting at 1.
- **Migration:** numbered SQL files, each run in one transaction at deploy time, before the new
  service revision takes traffic. The provider's point-in-time restore (7 days on the free
  tier, ASSUMED) is the backup. In v1, migrations are **additive only** (new tables, nullable
  columns, indexes), so the previous service revision keeps working against a newer schema.
- **Reverse:** no down-migrations. A failed migration rolls back its own transaction and the
  deploy stops, leaving the previous revision serving. A non-additive change is not allowed in
  v1.

## Interfaces

**Service API (HTTPS, JSON, one origin).** Every call except sign-in carries the session
cookie (`HttpOnly`, `Secure`, `SameSite=Lax`); state-changing calls also need the
`X-Dumpit-CSRF` header the app reads from a non-HttpOnly cookie.

```
POST /v1/auth/link          {email}                    → 202 (always; an email is sent if allowed)
GET  /v1/auth/callback?t=…                             → sets session cookie, redirects to the app
POST /v1/auth/sign-out                                 → 204 (this device's session revoked)
GET  /v1/me                                            → 200 {email, tz, monthly_budget_cents?}
PUT  /v1/me/tz              {tz}                       → 204

POST /v1/captures   {capture_id, text, source, captured_at, tz}
  → 200 {capture_id, status: "filed"|"note", lines: [LogLine], seq}   // same answer on a repeat
  → 400 malformed · 401 not signed in · 413 text > 4,000 chars
  → 429 daily capture limit (200/day) with Retry-After
  → 502 model output failed the schema check twice · 503 provider down or spend cap reached
POST /v1/captures/{id}/retry                            → as above
GET  /v1/changes?since=<seq>                            → 200 {items: [...], deleted: [...], seq}
GET  /v1/dashboard?today=YYYY-MM-DD                     → 200 {due_soon, month, active_trips}
GET  /v1/trips/{id}                                     → 200 {trip, todos, expenses, spent_cents}
POST /v1/tasks/{id}/done                                → 200 {seq}
POST /v1/undo   {batch_id | item: {kind, id}}           → 200 {result: "undone"|"conflict", seq}
POST /v1/redo   {batch_id | item: {kind, id}}           → 200 {result, seq}
POST /v1/push/subscribe     {endpoint, keys}            → 201
GET  /v1/health                                         → 200 {status, prompt_version, model, schema_version}
```

**Op schema** (the only things the model can propose; unchanged from slice 1):

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

**Validator rules** (`dumpit_ops`, shared by the service and the eval harness): every `ref`
exists, belongs to the user and is not deleted; dates are real calendar dates between 2 years
ago and 5 years ahead; `amount_cents` is 1 … 10,000,000; `category` is one of the 10 (else
*Other*); trip `end_date ≥ start_date`; a due time needs a due date; at most **5**
`update`/`delete`/`complete_task` ops per capture; a `paste` capture may contain only
`create_*` and `note` ops. A batch with any invalid op is rejected whole and the capture
becomes a note.

**Context snapshot** sent to the model (built on the server from the user's items): open
tasks (≤ 50) and the 10 latest done; expenses from the last 30 days (≤ 100); trips not ended
more than 30 days ago; the monthly budget.

**Trip to-do template** (offsets from `start_date`; any date before today is clamped to today):
book travel −42 d, book stay −35 d, check passport/ID −28 d, pay remaining balances −7 d,
pack −1 d.

**Eval harness (Phase 0):** `eval/captures.jsonl`, one case per line —
`{id, today, tz, context, text, source, expected_ops, author}`; `python -m eval.score` prints
per-kind and overall *fully correct* share (kind, amount, date, category, trip link all equal
after Validator normalisation) and mean cost per capture, separately for cases written by
the builder and by others, and writes `eval/report.json`.

## Failure modes

| What goes wrong | System does | Scenario |
|---|---|---|
| No connection when a capture is sent | Capture kept in the device outbox, shown as "Waiting to file"; sent automatically when the connection returns while the app is open, or the next time it is opened | capture sent while offline is filed after reconnecting |
| A relative date is said offline and filed the next day | Dates resolve against `captured_at`, not the filing time | relative date in a queued capture resolves to the day it was said |
| App closed or connection lost after the server filed a capture but before the device heard back | The capture stays in the outbox; resending it returns the stored answer, because the server is idempotent on `capture_id` | app closed mid-filing files the capture exactly once |
| Several captures sent quickly, or queued offline | Sent strictly oldest-first, one at a time, per device | captures are filed in the order they were said |
| Two devices send captures at the same time | The server files them one at a time per user (row lock on the user), in arrival order | two devices capturing at once never lose an item |
| Filing service or model provider returns an error | Two automatic retries (5 s, 30 s); then "Couldn't file this. Your words are saved" with Retry | filing service error keeps the words and offers retry |
| Daily capture limit or global spend cap reached | Captures stay waiting with the reason shown; filed when the limit resets | daily filing limit reached keeps captures waiting |
| Model output breaks the op schema | One model retry; a second failure is a 502, treated as a service error | invalid model output is never applied |
| Model output breaks a Validator rule | Whole batch rejected; capture kept as a note with suggestions | implausible amount is not filed as an expense |
| Capture is not understood | Kept as a note; up to 3 one-tap suggestions | capture that is not understood is kept as a note |
| A correction matches no item | Nothing changes; kept as a note | correction that matches nothing changes nothing |
| A correction matches several items | The most recent matching item changes; the log line names it, with Undo | correction applies to the most recent matching expense |
| Pasted text contains edits, deletions or instructions | Paste is create-only; the batch becomes a note | pasted notes cannot change or delete existing items |
| One capture tries to change many items | More than 5 changes rejects the batch to a note | one capture cannot change more than five existing items |
| Undo of an item a later capture changed | Refused for that item: "Changed since — say the correction instead" | undo of an item changed since is refused |
| Notifications not allowed on a device, or the web app was not added to the Home Screen on iPhone (Safari tabs cannot receive Web Push) | Task still filed; the Dashboard shows "Reminders are off on this device" with the steps to turn them on | reminders without notification permission warn the user |
| User travels to another time zone | Each device reports its zone when opened; future reminders go out at the same wall-clock time in the latest reported zone | reminder keeps its wall-clock time after a time zone change |
| A push subscription expires or is revoked by the browser | The push service answers 404/410; the subscription is deleted and the device asks again on next open | an expired push subscription is removed and not retried |
| Sign-in link opened after 15 minutes, or a second time | No session is created; the page says the link has expired and offers to send a new one | an old sign-in link does not sign anyone in |
| Device lost or stolen | From another device, Settings → Devices → Sign out that device revokes its session at once | signing out a lost device ends its access |
| Someone requests a sign-in link for an email that is not the user's | v1 has an allowlist of one email (ASSUMED single user); other addresses get the same 202 and no email | a sign-in link is only sent to the user's own email |
| Paste or typed text over 4,000 characters | Send disabled; text stays with a count and a message | capture over 4,000 characters is not sent |
| Trip departs sooner than the template offsets | Past to-dos are due today; none after departure | to-dos for a trip departing soon are due no later than departure |
| Expense inside two overlapping trips that names neither | Linked to the trip with the later start; the log line names it | expense inside two overlapping trips links to the later one |
| Month spending passes the budget | Bar turns warn colour; "€X over" replaces "left" | month over budget says how much over |
| Database migration fails on deploy | Transaction rolls back; deploy stops; previous revision keeps serving; data unchanged | failed database upgrade leaves data unchanged |
| A previous service revision is redeployed after a newer one changed the schema | Works, because v1 migrations are additive only | rolled-back service version reads data written by the newer version |
| iPhone clears website data for an unused web app | Only the outbox and cache live on the device; the next sign-in restores everything from the server. Unsent captures in the outbox would be lost, so the app files them as soon as it is online | cleared website data comes back on the next sign-in |

## Rollback

| Layer | How | Tested by |
|---|---|---|
| Code | The service and the web app ship together as one container image. Roll back by sending traffic to the previous Cloud Run revision (under a minute); the prompt and model are pinned in the image. The service worker checks for a new app version on each open, so devices pick up the rolled-back app on their next open. | CI drill: deploy N, then N−1; call `/v1/health`; run the 20-case eval smoke set and the web smoke scenarios against N−1. |
| Data | No down-migrations; v1 migrations are additive, so revision N−1 reads data written by N. A failed migration rolls back its own transaction. For data damage, the provider's point-in-time restore. User-level: undo/redo per capture. | Scenarios "failed database upgrade leaves data unchanged" and "rolled-back service version reads data written by the newer version" in the same drill. |

## Security and privacy

| Concern | Handling |
|---|---|
| Sensitive data | Spending, appointments, travel dates and places, and the words of every capture. Stored in Postgres in the EU, encrypted at rest by the provider, reached only by the service over TLS. Each device's outbox and read cache sit in that browser's storage. Each capture's text and a context snapshot go to the LLM provider for that one request (commercial API terms: no training on API data; the provider's abuse-monitoring retention is stated in the privacy notice). |
| Access control | Every query is scoped by the signed-in `user_id`; an automated test signs in as a second user and checks it sees nothing of the first. Sessions are per device and can be revoked. |
| Secrets | LLM API key, database URL, email provider key and the VAPID private key are Cloud Run secrets (Secret Manager), never in the web app or the repo. Sign-in link tokens and session tokens are stored only as SHA-256 hashes. |
| What gets logged | Request id, user id hash prefix, status, latency, token counts, op kinds and counts, prompt version. **Never** capture text, item titles, amounts or model output. No analytics SDK in the web app. |
| Abuse and cost | 200 captures/day per user; 4,000-char cap; global daily spend cap (default €2/day) after which filing returns 503; sign-in links rate-limited to 5 per hour per email. |
| Prompt injection | The model can only propose ops on the user's own data; the Validator enforces the schema, ref ownership, ranges, the 5-change limit and create-only pastes. Worst case: a wrong but visible filing with Undo. |
| Web security | One origin; `HttpOnly` `Secure` `SameSite=Lax` session cookie plus a CSRF header on writes; strict Content-Security-Policy; no third-party scripts. |
| GDPR | Single user who is also the data subject; EU region for the database and service; processors named in the privacy notice (database host, email provider, LLM provider, push services carry only an encrypted payload). "Delete my account" removes every row for the user; deleting the Home Screen app clears only that device. |

## Not built

Carried from the proposal: day-by-day itinerary generation; bank or card connection; receipt
photos and image/file drop (paste of text only); calendar integration; sharing, shared trips
and split costs; multiple currencies (EUR only); native App Store and Play Store apps (the web
app is installed from the browser; a Capacitor wrapper can follow); home-screen widget, watch
app and daily summary push; recurring items and per-category budgets; any assistant that
books, buys, emails or calls; chat or free-form questions about the data. Also not built in
v1, decided here: more than one user per deployment (sign-in allowlist of one email), live
push of changes between devices (polling on focus instead), passkeys, dark mode, crash
reporting, a custom voice recorder (the keyboard's dictation is used).

## Strongest counter-argument

**The design moves the hard problem into a place it cannot be tested before users arrive.**
The product lives or dies on the fully-correct filing rate on real people's words, and Phase 0
measures it against a test set the builder largely writes. Self-written captures are cleaner
than what people actually say; a model scoring 92 % on them can plausibly score 75–80 % on a
stranger's fortnight, and then the one-line confirmation becomes a review of every capture,
the very burden the product promises to remove. The context snapshot (≤ 50 tasks, 30 days of
expenses) also means corrections to older items silently fail to match.

Three further weak points. (1) **A web app gets little background time:** offline captures
are filed when the app is next open and online, not on their own, and reminders depend on
the user having added the app to the Home Screen and allowed notifications on each device.
(2) **The cloud copy raises the stakes:** the server now holds a person's spending,
appointments and travel plans; one access-control bug or leaked database URL exposes all of
it, where the earlier design could leak at most one phone. (3) **The proposal's recommended
concierge test has not been run**, so the build may answer a question nobody asked.

If only one change is made, the strongest is still: make Phase 0's test set include at least
50 captures written by people other than the builder, and gate Phase 1 on that subset's score.
