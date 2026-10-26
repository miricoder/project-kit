# Independent review: dumpit (round 1)

You are one of three independent reviewers, each from a different AI company. The plan below was written by Claude (Anthropic). Your job is to find what is wrong with it before anyone builds it. Be rigorous, not polite: a weak plan that passes costs far more than a strong plan that is questioned.

## Rules

1. Judge only what is in this case. Every finding cites the document and section it rests on, in `evidence`.
2. Rate every criterion below, exactly once.
3. This is a plan, not running software. Label each finding's confidence honestly; SPECULATING is acceptable when the plan neither confirms nor rules a risk out.
4. Every `blocker` and `major` finding carries a concrete `fix`: what to change, not just what is wrong.
5. Your verdict must agree with your findings: SOUND has no blockers and no failed criterion; FIX FIRST has at least one blocker; NEEDS INFO has at least one question.
6. Reply with exactly one JSON object in the format at the end, and nothing else.

## Verdicts

| Verdict | Meaning |
|---|---|
| `SOUND` | Buildable as written. Nothing must change before implementation starts. |
| `FIX FIRST` | The direction is right, but specific blocking problems must be fixed before implementation. Every one is a finding of severity `blocker` with a concrete fix. |
| `NEEDS INFO` | The case is missing something needed to judge it. Every gap is listed in `questions`. |
| `SPLIT` | This is more than one product or too large for one plan. Say where to cut in the findings. |
| `REJECT` | Fundamentally unsound: the core capability cannot work as designed, or the scope or cost is not credible. Say why in the findings. |

## Criteria

| id | Question |
|---|---|
| `job_fit` | Does v1 do the stated job end to end for the named person? |
| `scope` | Is the v1 cut the smallest thing that does the job, and does the spec stay inside it and its out-of-scope list? |
| `feasibility` | Can the core capability work as designed? Are the technical risks named and credible? |
| `failure_modes` | Is the failure-mode table complete, and does every row have an acceptance scenario? |
| `data_and_rollback` | Is the data model sound, are migrations versioned, and can both code and data be rolled back? |
| `security_privacy` | Is sensitive data identified and protected, are secrets kept out of code and logs? |
| `testability` | Are the acceptance criteria executable, and do they cover every v1 capability? |
| `cost` | Are the effort and running-cost estimates credible, and is the biggest uncertainty addressed? |
| `counter_argument` | Does the design survive its own strongest counter-argument? |

Rate each `pass`, `concern` or `fail`. A `concern` or `fail` needs a `note`.

## Findings

| Field | Values |
|---|---|
| `criterion` | one of the criteria ids |
| `severity` | `blocker` (must change before building), `major` (should change), `minor` (worth noting) |
| `confidence` | `CITED` (points at specific text), `REASONED` (follows from the text), `SPECULATING` (plausible, neither confirmed nor ruled out) |
| `claim` | what is wrong, in one or two sentences |
| `evidence` | the document and section, quoted where it helps |
| `fix` | the concrete change; required for blocker and major |

## Reply format

```json
{
  "form_version": 1,
  "case_id": "cf86ac898d9eb9d3",
  "verdict": "SOUND | FIX FIRST | NEEDS INFO | SPLIT | REJECT",
  "summary": "two or three sentences: the verdict and the main reason",
  "criteria": [
    {
      "id": "job_fit",
      "rating": "pass | concern | fail",
      "note": ""
    },
    {
      "id": "scope",
      "rating": "pass | concern | fail",
      "note": ""
    },
    {
      "id": "feasibility",
      "rating": "pass | concern | fail",
      "note": ""
    },
    {
      "id": "failure_modes",
      "rating": "pass | concern | fail",
      "note": ""
    },
    {
      "id": "data_and_rollback",
      "rating": "pass | concern | fail",
      "note": ""
    },
    {
      "id": "security_privacy",
      "rating": "pass | concern | fail",
      "note": ""
    },
    {
      "id": "testability",
      "rating": "pass | concern | fail",
      "note": ""
    },
    {
      "id": "cost",
      "rating": "pass | concern | fail",
      "note": ""
    },
    {
      "id": "counter_argument",
      "rating": "pass | concern | fail",
      "note": ""
    }
  ],
  "findings": [
    {
      "criterion": "scope",
      "severity": "blocker | major | minor",
      "confidence": "CITED | REASONED | SPECULATING",
      "claim": "",
      "evidence": "",
      "fix": ""
    }
  ],
  "questions": []
}
```

Copy `case_id` exactly: `cf86ac898d9eb9d3`. It binds your verdict to this version of the plan.

## The author's strongest counter-argument

The author was required to argue against their own design. Engage with it under `counter_argument`: does the design survive it?

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

## The case

===== BEGIN docs/research.md =====
# Research: Dumpit

> Phase 1 of the Project Kit pipeline. Every claim is marked VERIFIED (looked up this
> session) or ASSUMED (not checked). Nothing here is a design decision.
>
> Evidence note: app-store pages could not be opened directly from the research
> environment. Claims marked **VERIFIED (search)** come from search-result summaries of
> vendor listings and help pages fetched this session: the claim exists, but it is the
> vendor's own description, not a hands-on test.

## The idea in one paragraph

A phone app that does the admin of your life for you. Tasks, spending and plans live in
one place, but you never organise them yourself. You tell it things in passing ("paid 42
for groceries", "move the dentist to Friday", "I'm going to Lisbon for a long weekend in
March, about 600 all in"), or paste in messy notes, and it builds and maintains the lists,
budgets and itineraries for you. A trip becomes a day-by-day plan, a budget, a running
tally of what you've actually spent, and to-dos (book, pack, renew, pay) that come back as
reminders when they're due. You glance at a dashboard; the assistant carries the burden of
keeping it all straight.

## The job

- **Who:** A busy adult (ASSUMED: late 20s to 40s, working, smartphone-first) who has
  several open loops at once (a trip, a monthly budget, appointments, renewals) and is
  organised in intent but not in practice. They have tried a to-do app, a budgeting app
  and a notes app, and stopped maintaining at least one of them.
- **Trying to:** "Keep on top of everything without having to keep on top of the system."
  Say it once, in whatever words come to mind, and trust that it's been filed, totalled
  and will come back at the right moment.
- **Today they:** Split the job across several tools that each need upkeep: a to-do app
  (Todoist, Reminders), a budgeting app or spreadsheet, a calendar, a notes app or chat
  with themselves for trip ideas, and the occasional ChatGPT conversation to draft an
  itinerary that then lives nowhere. (ASSUMED, consistent with how the prior art below is
  positioned.)
- **It goes wrong when:** Upkeep lapses. An expense isn't logged because the budgeting app
  needs a category and an account; a trip itinerary from a chat never turns into tasks; the
  passport renewal sits in a note and is never surfaced; the "600 all in" trip budget is
  never compared with what was actually spent. Each tool works; the gaps between them and
  the maintenance they demand are where things fall through. (ASSUMED.)

## The one thing

**Reliable capture-to-structure.** A throwaway sentence or a pasted mess must land in the
right place, with the right amount, date and link (this expense belongs to the Lisbon
trip; this to-do is due two weeks before departure), *without the user checking*. If
people have to review and correct every entry, the burden is back on them and the product
is just another app to maintain.

## Prior art

| Product | Does the job? | Where it falls short | Evidence |
|---|---|---|---|
| **Expense Easy: AI Money Tracker** (iOS) | partly, closest | Money-and-travel focused: receipt, budget and travel agents working through conversation. General tasks and appointments are not part of its pitch; planned-vs-actual trip comparison listed as "Coming Soon". | VERIFIED (search) |
| **TripWise AI Trip Planner** (iOS) | partly | Strong for trips (day-by-day itinerary, budgets, expenses, tasks, pre-departure reminders, currency conversion), but scoped to trips. Everyday spending and life tasks sit outside it. Appears form-driven rather than "tell it in passing". | VERIFIED (search) |
| **Travely AI, Pro Travel Planner, Trailo, Trip Plan Go, Roamer** | partly | Same pattern: AI itinerary + cost estimate + some spending log. Travely compares logged spend to the AI estimate. All are trip-only. | VERIFIED (search) |
| **Volatier** | partly | Chat agent edits a day-by-day itinerary; budget tracker projects final costs. Trip-only. | VERIFIED (search) |
| **Todoist + Ramble** | partly | Excellent natural-language/voice capture of tasks (LLM, corrections mid-speech, dates and priorities extracted; GA Jan 2026, 38–40+ languages). No money, no budgets, no itineraries. User still organises projects. | VERIFIED (search) |
| **TalkieMoney, Gullak, AI Budget Assistant** | partly | Prove that "add a $40 grocery expense" by voice/text works. Money only. AI Budget Assistant can read bank notifications on Android. | VERIFIED (search) |
| **n8n / WhatsApp / Telegram expense bots** (DIY templates) | partly | Show demand for "text a bot and it logs it" into a sheet. Requires self-hosting and setup; one domain only. | VERIFIED (search) |
| **Carly** | no (different angle) | AI agent that reads and handles email-driven admin; from ~$35/month. Acts on inboxes, not on things you say in passing; no budgets or trip plans. | VERIFIED (search) |
| **Duckbill** | no (different angle) | Human-plus-AI errand service (e.g. calling insurers). Does tasks *for* you rather than organising your own information. | VERIFIED (search) |
| **Ayla, TaskPilot, LifeCTRL** | partly | Bill reminders / dumpit organisers. Ayla's page is stale; TaskPilot is a manual tracker; LifeCTRL is a tiny launch ("AI chief of staff"). | VERIFIED (search) |
| **ChatGPT / Gemini (general assistants)** | partly | Can draft an itinerary, budget or plan from messy notes, and have memory and scheduled reminders. But output is a conversation, not a maintained dashboard; memory is capacity-limited (one vendor estimate: ~100–200 facts before "Memory is full"; OpenAI publishes no figure). No running ledger. | VERIFIED (search) for memory limits; ASSUMED for reminder behaviour |
| **YNAB / Monarch** (budgeting) | partly | Mature budgeting and bank sync. Manual categorisation and upkeep is the core workflow, the opposite of "effortless". | ASSUMED |
| **TripIt** | partly | Builds itineraries automatically from forwarded booking emails. No budget-vs-actual, no general tasks. | ASSUMED |
| **Notion (+ AI)** | partly | Can hold all three domains in one place, but the user builds and maintains the system. | ASSUMED |

**Closest alternative:** **Expense Easy**, with **TripWise** close behind for the trip
half. Both show that conversational budget + trip planning is already shipping as of 2026,
so "AI trip planner with a budget" alone is not differentiated. What none of the found
products claim is the combination this idea rests on: **one capture surface across
everyday tasks, everyday spending and trips, with the assistant maintaining links between
them** (a grocery expense goes to the monthly budget; a Lisbon dinner goes to the trip and
the month; "renew passport" is created from the trip and scheduled backwards from the
departure date). That is a real gap, but it is a gap in *integration and upkeep*, not in
any single feature. Honestly: the risk is that incumbents (Todoist adding money, ChatGPT
adding structured trackers, a trip app adding general tasks) close it from one side.

## Constraints

| Dimension | Answer | Evidence |
|---|---|---|
| Platforms | Phone first (iOS and/or Android, not yet decided); a glanceable widget or home-screen surface likely matters | ASSUMED from "a phone app" |
| Offline | Nice-to-have: capture should work offline and sync later (abroad on a trip with poor data is a core scenario); structuring may need a connection | ASSUMED |
| Data stored | Personal finances (amounts, merchants, possibly receipts), calendar-like appointments, travel plans and dates, free-text notes. **High sensitivity**: financial plus location/travel patterns | ASSUMED |
| Accounts / auth | Likely needed so data survives a lost phone and syncs across devices; not necessarily needed for a single-device v1 | ASSUMED |
| Who else sees the data | Nobody by default. Shared trips or household budgets are an obvious later ask (splitting Lisbon costs with a partner) | ASSUMED |

## What nobody knows yet

Most consequential first.

1. **How accurate does capture need to be before people stop checking it?** The product
   only removes the burden if users trust it unseen. Settled by: a test with real users
   logging a week of real life by voice/text, measuring the share of entries that are
   filed, amounted, dated and linked correctly, and how often they open the app to fix
   things.
2. **What happens when it is wrong, and how does the user notice?** A wrong amount or a
   reminder filed under the wrong date fails silently. Settled by: deciding what the
   user sees after each capture (a confirmation line? nothing?) and testing which keeps
   trust without becoming a chore.
3. **Will people actually tell it things in passing?** Todoist Ramble and the expense bots
   suggest yes for single domains; whether people narrate *mixed* life admin to one app
   is unproven. Settled by: a concierge/Wizard-of-Oz test (a chat thread where a human
   plays the agent) for two weeks with five to ten people.
4. **Does spending need bank or card data, or is spoken logging enough?** Spoken logging
   is effortless per entry but easy to forget; bank sync is complete but costly, regulated
   and region-specific. Settled by: the concierge test (how many real purchases go
   unlogged?) and a cost/regulation check per target market.
5. **How much should it act versus organise?** "Move the dentist to Friday" might mean
   update a reminder, or edit a real calendar event, or call the dentist. Settled by:
   asking users which they expect, and deciding whether calendar integration is in scope.
6. **Who pays, and how much?** Comparable AI tools range from one-off small purchases
   (TaskPilot $3.99) to ~$35/month (Carly), and running an LLM on every capture has real
   per-user cost. Settled by: per-capture cost estimate plus a willingness-to-pay survey
   or pricing test.
7. **Which market and currency first?** The examples ("42", "600 all in", Lisbon) suggest
   a Euro or UK user, which affects currency handling, data-protection rules (GDPR) and
   which bank-data options exist. Settled by: the user stating the first target market.
8. **Is "dashboard you can glance at" a screen, a widget, or a daily summary?**
   Settled by: user interviews on where they would actually look.

## Explicitly not researched

- Technology, architecture, models or hosting: deliberately left to `/design`.
- Bank-data aggregation providers, their coverage and pricing.
- Legal and regulatory requirements (GDPR specifics, financial-data rules, app-store
  policy on AI agents).
- App-store ratings, downloads and user reviews of the alternatives (the listings could
  not be opened directly; only search summaries were read).
- Booking and travel-inventory integrations (flights, hotels).
- Market sizing and competitor revenue.
- Accessibility needs and languages beyond English.
===== END docs/research.md =====

===== BEGIN docs/proposal.md =====
# Proposal: Dumpit

> Phase 2 of the Project Kit pipeline. Scope and cost. No architecture — that is /design.
> Built from `docs/research.md`. Assumptions inherited from research (Euro/UK user,
> single person, phone first) still stand until the user corrects them.

## v1 in one sentence

One person types, dictates or pastes life admin into a single box on their phone, and the
app files it, correctly and without being checked, as tasks with reminders, expenses
against a monthly budget, and trips with a budget, a spent-so-far total and
backward-scheduled to-dos, all visible on one glanceable dashboard.

## What v1 does

- **One capture box.** Typed text, the phone's built-in dictation, or a pasted block of
  messy notes. No forms, no category pickers, no "which list?" question.
- **Turns each capture into one or more items** of three kinds, and can split one
  sentence or paste into several ("paid 42 for groceries and book the car service" → one
  expense, one task):
  - **Task:** title, optional due date/time, a reminder notification when due.
  - **Expense:** amount, date, a category it picks itself, and the trip it belongs to
    if one is active or named.
  - **Trip:** name, dates, total budget ("Lisbon, long weekend in March, about 600 all
    in").
- **Edits by saying so.** "Move the dentist to Friday", "that was 24 not 42", "cancel the
  car service": it finds the item and changes it.
- **Trip upkeep, done for you.** Creating a trip generates a standard set of to-dos (book
  travel, book stay, check passport/ID, pack, pay balances), each scheduled backwards from
  the departure date. Expenses logged during or for the trip count against its budget, and
  the trip shows budget, spent, remaining.
- **One monthly budget.** A single monthly spending figure, totals by category the app
  chose, spent vs remaining. Trip spending appears in both the trip and the month.
- **Shows what it did after every capture.** One line per item ("Expense €42 · Groceries ·
  today") with a one-tap undo. This is how mistakes get noticed (research Q2) without
  making the user review a form.
- **The dashboard.** One screen: due and overdue tasks, this month's budget, active
  trip(s) with spent vs budget and next to-dos.
- **Capture works offline.** Anything entered without a connection is kept and filed when
  the connection returns; the user sees it as "waiting to file".

## What v1 explicitly does not do

- **No day-by-day itinerary generation.** The trip in v1 is budget + spending + to-dos.
  Generating a daily plan is a different problem (recommendations, opening hours, travel
  times) and the job ("keep on top of it") is done without it. First thing in Phase 3.
- **No bank or card connection.** Spending is what the user tells it. Bank data is
  costly, regulated and region-specific (research Q4); the concierge test decides
  whether it is ever needed.
- **No receipt photos or file/image drop.** Text and pasted text only. "Drop in" from the
  brief is limited to paste.
- **No calendar integration.** "Move the dentist to Friday" moves the app's own task, not
  an event in Google/Apple Calendar, and nobody gets phoned.
- **No accounts, cloud sync or second device.** Data lives on the one phone. Losing the
  phone loses the data; v1 is for one person proving the idea. (Phase 4.)
- **No sharing.** No shared trips, split costs or household budgets.
- **No multiple currencies.** One home currency (assumed EUR). Spending in another
  currency must be entered in the home currency.
- **One phone platform only** (iOS or Android, chosen in /design). The other platform,
  tablets and web come later.
- **No home-screen widget, watch app or daily summary push.** The dashboard is a screen
  in the app. (Phase 3 for the widget.)
- **No recurring items** (rent every month, a weekly bin reminder) and **no
  multi-category budgets** (a separate limit per category).
- **No assistant that acts in the world**: no booking, buying, emailing or calling.
- **No chat or Q&A** ("how much did I spend on food in February?"). The dashboard answers
  the common questions; free-form questions are Phase 3.

## Phases

| Phase | Delivers | Acceptance criteria | Effort |
|---|---|---|---|
| 0 | **Foundation: the filing test set.** A written collection of at least 200 realistic captures (single sentences, mixed sentences, edits, three pasted messy notes) with the correct filed result for each, and a way to score the filing against it. | The set exists, covers all three item kinds plus edits and pastes, and a single run prints the share of captures filed fully correctly (kind, amount, date, category, trip link). A first baseline score is recorded. | 2–4 sessions |
| 1 | **Capture, tasks, expenses, dashboard.** Capture box, task and expense filing, edit-by-saying, monthly budget, after-capture line with undo, reminders, offline queue, dashboard. | (a) ≥ 90% of the Phase 0 set's task and expense captures are filed fully correctly. (b) A task captured as "dentist Thursday 3pm" raises a notification at that time with the phone locked. (c) A capture entered in airplane mode appears as "waiting to file" and is filed within 30 s of reconnecting. (d) Undo restores the previous state in one tap. (e) "That was 24 not 42" changes the most recent matching expense, verified on 20 test edits with ≥ 18 correct. | 6–10 sessions |
| 2 | **Trips.** Trip creation from a sentence, backward-scheduled to-dos, trip budget vs spent vs remaining, trip expenses counting in both trip and month. **End of v1.** | (a) "Lisbon long weekend 13–16 March, about 600 all in" creates a trip with those dates and €600 budget, and at least five to-dos each with a due date before 13 March. (b) An expense captured with "Lisbon" or during the trip dates is linked to the trip in ≥ 90% of the Phase 0 trip cases. (c) The trip view's spent total equals the sum of its linked expenses. (d) The whole Phase 0 set scores ≥ 90% fully correct. (e) One person uses it as their only dumpit tool for 14 days and opens a fix/undo on fewer than 1 in 10 captures. | 4–7 sessions |
| 3 | **Planning and glance.** Day-by-day itinerary for a trip (generated, then editable by saying), home-screen widget, ask-a-question ("how much on food this month?"), recurring items. | A generated Lisbon plan has one entry per day for the trip dates and stays within the stated budget estimate; the widget shows next task and month remaining without opening the app; 18/20 test questions answered with the right figure. | 6–10 sessions |
| 4 | **Keep it safe and share it.** Account, backup and sync, second device, shared trips with cost split, multiple currencies. | Data entered on phone A appears on phone B within a minute; a reinstall restores all data after sign-in; a shared trip shows each person's spend and who owes whom. | 8–14 sessions |

Acceptance criteria are observable conditions, not activities.

## Cost

| Kind | Estimate | Driven by |
|---|---|---|
| Build effort, v1 (Phases 0–2) | **12–21 working sessions** | How quickly filing reaches 90%: prompt/rule iteration against the Phase 0 set is the unknown part; screens and reminders are predictable. |
| Build effort, Phases 3–4 | 14–24 further sessions | Sync and sharing (Phase 4) carry most of the spread. |
| Running cost, model calls | **≈ €0.001–0.01 per capture** → for one heavy user (~20 captures/day, ~600/month) **€0.60–6 per user per month**; for the builder alone during v1, under €10/month. | Size of model needed to hit 90%, length of pasted notes (a long paste can cost 10–20× a sentence), and whether each capture needs one call or several. |
| Running cost, hosting | **€0–20/month** in v1 (at most a small service so the model key is not on the phone); Phase 4 sync adds roughly €10–50/month at small scale. | Whether v1 calls the model directly or through a minimal server; storage and sync volume later. |
| Store fees | Apple developer programme ~€99/year, or Google Play one-off ~€25. | Platform choice. |

**Biggest uncertainty:** whether a small, cheap model can file mixed captures at ≥ 90%
fully correct. If it needs a large model or several calls per capture, per-user cost rises
toward the top of the range (or above it) and Phase 1–2 effort moves to the high end.
Phase 0 exists to find this out before the rest is built.

## Risks carried forward

| Risk | If it goes wrong | Carried because |
|---|---|---|
| Filing accuracy stalls below the level where people stop checking (research Q1). | The product becomes another app to maintain: the core promise fails. | Only building and measuring settles it; Phase 0–1 criteria make it visible early. |
| People don't narrate mixed life admin to one app (research Q3). | Usage dries up after the novelty; the single capture box has no advantage over Todoist + a budget app. | Recommended concierge test (below) is cheap but needs real participants; not run yet. |
| Spoken/typed spending misses too many purchases (research Q4). | Budgets look wrong, trust falls, bank data becomes necessary (cost, regulation). | v1 deliberately excludes bank data; Phase 2's 14-day use will show how much goes unlogged. |
| Data loss: single-device, no backup in v1. | A lost or reset phone wipes everything; a tester abandons it. | Accepted for a one-person proof; fixed in Phase 4. |
| Users expect "move the dentist" to change their real calendar (research Q5). | Confusion and duplicated appointments. | Calendar integration excluded from v1; revisit after the 14-day use. |
| Pricing unknown (research Q6). | Per-user model cost exceeds what people will pay. | No users yet; Phase 0 gives the real per-capture cost to price against. |
| Target market and currency unconfirmed (research Q7). | Wrong currency default, wrong privacy rules. | Assumed EUR/GDPR; needs the user's answer. |
| Fast followers: Todoist, ChatGPT or a trip app adds the missing domains. | Differentiation narrows to integration quality. | Market risk, not resolvable by scope. |

## Decision

**Recommend: accept, with one cheap step first.** Before Phase 1, run the concierge test
from the research: five to ten people send their real life admin to a chat thread for two
weeks while a person files it by hand. It costs no build effort and answers research Q3
and Q4, the two risks the build cannot answer. If people stop sending after a few days,
stop or rethink before spending 12–21 sessions.

The cut that matters most: **day-by-day itineraries are out of v1.** They were in the
original brief, but the job (keep on top of a trip's money and to-dos without upkeep) is
done without them, and they are the riskiest feature to get right. If the itinerary is
the part you care most about, say so: it would swap places with the monthly budget in
v1 and add roughly 3–5 sessions.
===== END docs/proposal.md =====

===== BEGIN docs/spec.md =====
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
===== END docs/spec.md =====

===== BEGIN docs/acceptance.feature =====
# Acceptance criteria for Dumpit v1 (proposal Phases 0–2).
# Contract for /test. Scenario names that appear in docs/spec.md "Failure modes" must match exactly.
# Unless a scenario says otherwise: today is Monday 23 February 2026, 09:00, time zone
# Europe/Lisbon, home currency EUR, the phone is online, and the store is empty.

Feature: Filing test set (Phase 0)

  Scenario: filing test set reports a fully-correct score
    Given the filing test set holds 200 captures covering tasks, expenses, trips, edits and 3 pasted notes
    When the scorer is run against the filing service
    Then it prints the share of captures filed fully correctly for each item kind and overall
    And it prints the mean cost per capture in euros
    And it writes eval/report.json with one result per capture id

  Scenario: tasks and expenses reach the Phase 1 accuracy bar
    Given the task and expense captures in the filing test set
    When the scorer is run against the filing service
    Then at least 90% of those captures are filed fully correctly

  Scenario: the whole test set reaches the v1 accuracy bar
    Given all 200 captures in the filing test set
    When the scorer is run against the filing service
    Then at least 90% of them are filed fully correctly


Feature: Capture and filing

  Scenario: a typed expense is filed against the month
    Given a monthly budget of €1,400
    When the user sends "paid 42 for groceries"
    Then an expense of €42.00 dated 23 February 2026 in category "Groceries" exists
    And the capture log shows the line "Expense €42 · Groceries · today" with an Undo button
    And the February budget shows €42 spent and €1,358 left

  Scenario: a task with a day and time is filed with a reminder
    When the user sends "dentist Thursday 3pm"
    Then a task "Dentist" due Thursday 26 February 2026 at 15:00 exists
    And a reminder notification is scheduled for 26 February 2026 at 15:00

  Scenario: a reminder fires with the phone locked
    Given a task "Dentist" due Thursday 26 February 2026 at 15:00
    And the phone is locked and the app is not running
    When the clock reaches 26 February 2026 at 15:00
    Then a notification "Dentist" is shown within 60 seconds

  Scenario: one sentence becomes two items
    When the user sends "paid 42 for groceries and book the car service"
    Then exactly one expense of €42.00 in category "Groceries" exists
    And exactly one task "Book the car service" with no due date exists
    And the capture log shows two filed lines, each with its own Undo button

  Scenario: an expense without a date is filed as today
    When the user sends "coffee 3.50"
    Then an expense of €3.50 dated 23 February 2026 exists

  Scenario: the monthly budget is set by saying it
    When the user sends "my budget is 1400 a month"
    Then the Dashboard shows a February budget of €1,400 with €1,400 left

  Scenario: dictated text is filed like typed text
    Given the keyboard's dictation has put "paid 42 for groceries" in the capture box
    When the user taps Send
    Then an expense of €42.00 in category "Groceries" exists

  Scenario: capture that is not understood is kept as a note
    When the user sends "the thing with Marta"
    Then no task, expense or trip is created
    And the capture log shows "Saved as a note. Is it one of these?" with at most 3 suggestions

  Scenario: implausible amount is not filed as an expense
    When the user sends "paid 4200000 for coffee"
    Then no expense is created
    And the capture is kept as a note

  Scenario: capture over 4,000 characters is not sent
    Given the capture box holds 4,001 characters
    When the user taps Send
    Then nothing is sent to the filing service
    And the text is still in the capture box
    And the message "Too long to file in one go: 4,001 of 4,000 characters" is shown

  Scenario: captures are filed in the order they were said
    Given the phone is offline
    And the user has sent "paid 42 for groceries" and then "that was 24 not 42"
    When the connection returns
    Then exactly one Groceries expense exists and its amount is €24.00


Feature: Edit by saying so

  Scenario: a task is moved by saying so
    Given a task "Dentist" due Thursday 26 February 2026 at 15:00
    When the user sends "move the dentist to Friday"
    Then the task "Dentist" is due Friday 27 February 2026 at 15:00
    And the reminder for 26 February is cancelled and one for 27 February at 15:00 is scheduled
    And the capture log shows "Moved · Dentist → Fri 27 Feb, 15:00" with an Undo button

  Scenario: an amount is corrected by saying so
    Given an expense of €42.00 "groceries" dated 23 February 2026
    When the user sends "that was 24 not 42"
    Then that expense's amount is €24.00
    And no new expense is created

  Scenario: a task is cancelled by saying so
    Given a task "Book the car service" with no due date
    When the user sends "cancel the car service"
    Then the task "Book the car service" no longer appears on the Dashboard

  Scenario: correction applies to the most recent matching expense
    Given an expense of €42.00 "groceries" dated 20 February 2026
    And an expense of €42.00 "groceries" dated 23 February 2026
    When the user sends "that was 24 not 42"
    Then the expense dated 23 February 2026 is €24.00
    And the expense dated 20 February 2026 is still €42.00

  Scenario: correction that matches nothing changes nothing
    Given an expense of €42.00 "groceries" dated 23 February 2026
    When the user sends "that was 15 not 80"
    Then no expense, task or trip is changed
    And the capture is kept as a note

  Scenario: twenty test corrections meet the Phase 1 bar
    Given 20 correction captures from the filing test set, each with its starting items
    When each correction is sent
    Then at least 18 change exactly the intended item and nothing else

  Scenario: one capture cannot change more than five existing items
    Given 6 open tasks whose titles contain "call"
    When the user sends "cancel all the calls"
    Then all 6 tasks are still open
    And the capture is kept as a note


Feature: Undo and redo

  Scenario: undo restores the previous state in one tap
    Given the user sent "paid 42 for groceries" and an expense of €42.00 was filed
    When the user taps "Undo expense €42 groceries"
    Then no Groceries expense exists
    And the February spent figure goes back to its value before the capture
    And the button now reads "Redo"

  Scenario: redo re-applies an undone item
    Given the user undid the expense of €42.00 groceries
    When the user taps "Redo"
    Then an expense of €42.00 in category "Groceries" exists again

  Scenario: undo of a move restores the old due date
    Given the user sent "move the dentist to Friday" and the task moved from 26 to 27 February
    When the user taps Undo on that line
    Then the task "Dentist" is due Thursday 26 February 2026 at 15:00
    And a reminder is scheduled for 26 February 2026 at 15:00

  Scenario: undo of an item changed since is refused
    Given the user sent "paid 42 for groceries"
    And then sent "that was 24 not 42"
    When the user taps Undo on the first capture's line
    Then the expense is still €24.00
    And the message "Changed since — say the correction instead" is shown

  Scenario: undo all reverts every item from a paste
    Given a pasted note produced 6 items
    When the user taps "Undo all"
    Then none of the 6 items exists


Feature: Pasted notes

  Scenario: a pasted note becomes several items
    Given the clipboard holds the text:
      """
      groceries 38.20
      dentist thu 3pm
      lisbon hotel deposit 120
      renew gym
      """
    And a trip "Lisbon" from 13 to 16 March 2026 exists
    When the user taps Paste and then Send
    Then 4 items are filed: an expense of €38.20, a task "Dentist" due 26 February at 15:00, an expense of €120.00 linked to "Lisbon", and a task "Renew gym"
    And the Pasted notes screen shows "Filed 4 items" with an "Undo all" button

  Scenario: pasted notes cannot change or delete existing items
    Given a task "Dentist" due Thursday 26 February 2026 at 15:00
    And the clipboard holds "cancel the dentist. groceries 12"
    When the user taps Paste and then Send
    Then the task "Dentist" is still due 26 February 2026 at 15:00
    And no expense is created
    And the capture is kept as a note

  Scenario: the paste button is disabled with an empty clipboard
    Given the clipboard is empty
    When the Dashboard is shown
    Then the Paste button is disabled


Feature: Offline and service failures

  Scenario: capture sent while offline is filed after reconnecting
    Given the phone is in airplane mode and the app is open
    When the user sends "paid 42 for groceries"
    Then the capture log shows "Waiting to file · you were offline"
    And when airplane mode is turned off an expense of €42.00 exists within 30 seconds
    And the waiting row is replaced by "Expense €42 · Groceries · today"

  Scenario: relative date in a queued capture resolves to the day it was said
    Given the phone was offline on Monday 23 February 2026 at 22:00
    And the user sent "dentist tomorrow 3pm" then
    When the connection returns on Tuesday 24 February 2026 at 08:00
    Then the task "Dentist" is due Tuesday 24 February 2026 at 15:00

  Scenario: app closed mid-filing files the capture exactly once
    Given the user sent "paid 42 for groceries"
    And the app was closed after the filing service replied but before the result was saved
    When the app is opened again
    Then exactly one expense of €42.00 exists

  Scenario: filing service error keeps the words and offers retry
    Given the filing service returns an error for every request
    When the user sends "paid 42 for groceries"
    Then after 2 automatic retries the capture shows "Couldn't file this. Your words are saved; nothing was lost."
    And a Retry button is shown
    And when the service recovers and the user taps Retry an expense of €42.00 exists

  Scenario: invalid model output is never applied
    Given the model returns output that breaks the op schema twice for the same capture
    When the user sends "paid 42 for groceries"
    Then no item is created or changed
    And the capture shows "Couldn't file this. Your words are saved; nothing was lost." with Retry

  Scenario: daily filing limit reached keeps captures waiting
    Given this install has filed 200 captures today
    When the user sends "paid 42 for groceries"
    Then the capture shows "Waiting to file · daily limit reached, files tomorrow"
    And no expense is created today


Feature: Reminders

  Scenario: reminders without exact alarm permission warn the user
    Given the app does not have the exact alarm permission
    When the user sends "dentist Thursday 3pm"
    Then the task is filed and a reminder is scheduled
    And the Dashboard shows a banner "Reminders may be a few minutes late" with a button to the setting

  Scenario: reminder keeps its wall-clock time after a time zone change
    Given a task "Dentist" due Thursday 26 February 2026 at 15:00 created in Europe/Lisbon
    When the phone's time zone changes to Europe/Berlin
    Then the reminder is scheduled for 26 February 2026 at 15:00 Europe/Berlin

  Scenario: ticking a task done cancels its reminder
    Given a task "Dentist" due Thursday 26 February 2026 at 15:00
    When the user ticks the task's checkbox
    Then no reminder for "Dentist" is scheduled


Feature: Monthly budget and dashboard

  Scenario: the dashboard shows due tasks, the month and the active trip
    Given a monthly budget of €1,400 and €912 of February expenses
    And a task "Check passport expiry" due today
    And a trip "Lisbon" from 13 to 16 March 2026 with a budget of €600 and €214 spent
    When the Dashboard is opened
    Then "Due soon" lists "Check passport expiry" marked "Today"
    And the month card shows "€488 left" and "€912 spent"
    And the trip card shows "€386 left" of €600

  Scenario: month totals by category show the top three
    Given February expenses of €300 Groceries, €200 Eating out, €150 Transport and €50 Fun
    When the Dashboard is opened
    Then the month card lists Groceries €300, Eating out €200 and Transport €150 and not Fun

  Scenario: month over budget says how much over
    Given a monthly budget of €1,400 and €1,450 of February expenses
    When the Dashboard is opened
    Then the month card shows "€50 over" instead of an amount left
    And the progress bar is full

  Scenario: a dashboard with nothing due says so
    Given no task is due in the next 7 days
    When the Dashboard is opened
    Then the "Due soon" card shows "Nothing due this week."


Feature: Trips

  Scenario: a trip is created from one sentence with backward-scheduled to-dos
    When the user sends "Lisbon long weekend 13–16 March, about 600 all in"
    Then a trip "Lisbon" from 13 March 2026 to 16 March 2026 with a budget of €600 exists
    And the trip has 5 to-dos, each due before 13 March 2026:
      | to-do                   | due              | why                                   |
      | Book travel             | 23 February 2026 | 42 days before is past, so due today  |
      | Book stay               | 23 February 2026 | 35 days before is past, so due today  |
      | Check passport/ID       | 23 February 2026 | 28 days before is past, so due today  |
      | Pay remaining balances  | 6 March 2026     | 7 days before departure               |
      | Pack                    | 12 March 2026    | 1 day before departure                |

  Scenario: to-dos for a trip departing soon are due no later than departure
    When the user sends "Porto this Friday to Sunday, 250 budget"
    Then a trip "Porto" from 27 February 2026 to 1 March 2026 exists
    And every to-do of that trip is due between 23 February 2026 and 26 February 2026

  Scenario: an expense that names the trip is linked to it
    Given a trip "Lisbon" from 13 to 16 March 2026
    When the user sends "lisbon hotel deposit 120"
    Then an expense of €120.00 dated 23 February 2026 is linked to the trip "Lisbon"
    And it also counts in February's spending

  Scenario: an expense during the trip dates is linked by date
    Given a trip "Lisbon" from 13 to 16 March 2026
    And today is 14 March 2026
    When the user sends "coffee 3.50"
    Then the expense of €3.50 is linked to the trip "Lisbon"

  Scenario: expense inside two overlapping trips links to the later one
    Given a trip "Lisbon" from 13 to 16 March 2026
    And a trip "Sintra" from 15 to 15 March 2026
    And today is 15 March 2026
    When the user sends "lunch 18"
    Then the expense of €18.00 is linked to the trip "Sintra"
    And the capture log line names "Sintra" with an Undo button

  Scenario: trip spent equals the sum of its linked expenses
    Given a trip "Lisbon" with linked expenses of €120.00, €3.50 and €90.50
    When the Trip screen for "Lisbon" is opened
    Then it shows €214 spent and €386 left of €600

  Scenario: trip without a budget shows no budget set
    When the user sends "Madrid 2 to 5 April"
    Then the trip card for "Madrid" shows "No budget set"

  Scenario: fewer than one in ten captures need a fix during 14 days of use
    Given one person has used Dumpit as their only life-admin capture tool for 14 days
    When their captures and undo or correction actions are counted
    Then fewer than 1 in 10 captures were followed by an undo or a correction


Feature: Data safety on upgrade and rollback

  Scenario: failed database upgrade leaves data unchanged
    Given a store at schema 1 with 50 expenses and 10 tasks
    And a migration to schema 2 that fails partway
    When the app is updated and opened
    Then the store is still at schema 1 with 50 expenses and 10 tasks
    And a copy named "dumpit.v1.bak" exists
    And the app shows "Couldn't finish updating your data. Nothing was lost."

  Scenario: rolled-back app version opens data written by the newer version
    Given app build N wrote a store at schema 2 with min_reader_version 1 holding 50 expenses
    When build N−1, rebuilt with a higher version code, is installed over it
    Then the Dashboard opens without error
    And all 50 expenses are listed with their amounts unchanged
===== END docs/acceptance.feature =====
