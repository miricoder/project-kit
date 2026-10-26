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
