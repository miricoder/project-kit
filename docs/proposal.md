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
