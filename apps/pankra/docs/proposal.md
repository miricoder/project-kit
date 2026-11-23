# Proposal: PANKRA

> Phase 2 of the Project Kit pipeline. Scope and cost. Architecture is in spec.md.

## v1 in one sentence

One athlete plans, logs, analyses and soundtracks his Hyrox and CrossFit training in one
iOS and web app, with every AI job run by registry skills on Claude or GPT.

## What v1 does

- **Today and Week:** whiteboard cards for each session; a week view with status (Done,
  Today, Scheduled, Moved, Skipped) and results beside each day.
- **Add class:** a box class from a screenshot or text replaces the day's plan and pushes
  later sessions to the next free days, keeping a rest day.
- **Log:** results typed or read from screenshots (confirmed before saving), with feedback.
- **Races:** Hyrox splits, seconds to gain per segment against the target.
- **Paces:** targets per machine from his own runs; Strava sync.
- **Fuel:** meals before and after from a fridge photo; race-morning plan.
- **Share:** the day's workout as a 1080 × 1350 Instagram image.
- **Skills graph:** every skill, agent, plugin and provider as an interactive node graph;
  hover shows connections and run order, click runs the node.
- **Keys:** Claude and GPT keys entered in the app, encrypted, kept for a retention period the
  user picks, deleted on expiry or on request.
- **Registry sync:** the app pulls skills, agents and plugins from project-kit's `registry/`
  by itself.

## What v1 explicitly does not do

- Other users, coaches, teams — one user now; every record keeps `userId` for later.
- Android — iPhone and web cover the owner.
- App Store or TestFlight release — needs the paid Apple account; v1 installs from Xcode.
- Session music (Spotify or Apple Music) — future R&D and integration; the service is not chosen.
- Push notifications, Sign in with Apple — both need the paid Apple account.
- Roxfit or Hyrox API integration — no known public API; screenshots instead (R&D later).
- Llama or other providers — the adapter makes them a later addition, not a v1 one.
- Payments, social feed, wearables beyond Strava.

## Phases

| Phase | Delivers | Acceptance criteria | Effort |
|---|---|---|---|
| 0 | Foundation | Web app and API deployed over https; owner signs in; CI green on `main` | 1–2 sessions |
| 1 | Training core | A week of sessions shows as cards; adding a class moves later sessions and keeps a rest day | 2–3 sessions |
| 2 | LLM layer | A skill runs on Claude and on GPT; a missing key blocks the run and asks for it; a key past retention is gone | 2–3 sessions |
| 3 | Registry and graph | Registry sync loads 13 nodes from project-kit; hovering an agent lights its steps in order; clicking runs it | 2 sessions |
| 4 | Data in | Strava runs arrive by webhook; a Hyrox screenshot becomes confirmed splits; race analysis shows | 2–3 sessions |
| 5 | Fuel and share | Meals from a fridge photo; a 1080 × 1350 PNG post exports | 1–2 sessions |
| 6 | iPhone | The app installs from Xcode on the owner's iPhone and shows the same week as the web app | 1 session |

## Cost

| Kind | Estimate | Driven by |
|---|---|---|
| Build effort | 11–16 working sessions | Screenshot reading is the least predictable |
| Running cost | $0–15 a month hosting on free tiers; LLM use $5–30 a month | Number of runs and image size; a monthly cap per provider stops runs past it |
| One-off | $0 (free Apple account); $99 a year if upgraded | Distribution choice |

**Biggest uncertainty:** the free Apple account's 7-day reinstall, which may prove too
tedious and force the $99 upgrade.

## Risks carried forward

- The 7-day reinstall from the owner's Mac may prove tedious enough to force the paid account.
- Screenshot reading accuracy across apps that change their layouts.
