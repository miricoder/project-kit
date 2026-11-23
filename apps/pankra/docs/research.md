# Research: PANKRA

> Phase 1 of the Project Kit pipeline. Written from the owner's own training workflow, run
> for a week as a chat with Claude (22–23 Nov 2026) before any code.

## The job

A hybrid athlete racing Hyrox Men's Pro (target: sub-60 minutes; checkpoint race HYROX
Chicago, 11–15 Feb 2027) who also trains at a CrossFit box wants **one place** that:

1. plans each day as a clear whiteboard card he can follow in the gym without asking
   questions (flow, rest, machine, mat lengths, timer settings);
2. takes his results — typed, or as screenshots from Hyrox, Roxfit, Runna, Strava and the
   box's app — and tells him what they mean;
3. reshuffles the week when the box programmes a class;
4. tracks paces per machine (Air runner, motorised treadmill, track), which differ a lot;
5. suggests food from what is in the fridge, and posts the day's workout to Instagram;
6. plays the right music for each part of the session (future R&D, after v1).

Today this is spread over five apps and a chat. The chat worked because a model did the
analysis; the app keeps that, and makes the model swappable (Claude or GPT).

## What the week of chat showed

| Finding | Evidence | Design consequence |
|---|---|---|
| Stations, not running, cost the most time | DC 2026: runs 31:26 (rank 68), stations 35:54 | Analysis ranks segments by seconds to gain |
| Air runner speed is much lower than treadmill speed at the same effort | ~13 km/h on Air runner vs 15 km/h held on a treadmill | Paces stored per machine, from his own data |
| Prescriptions must be fully spelled out | Repeated questions on run order, rest, sled lengths | Card rules are a contract (`workout-whiteboard`) |
| Box classes arrive at short notice | Two classes inserted in two days | Schedule shifting is a core feature |
| The card look matters to him | Rejected a table format for workouts | Cards are the only workout format |
| Pre-race fuel changed a result | Candy bar before Poznań, runs ~2 min/km slower | Race-morning plan in the fuel feature |

## Prior art

| Product | Does well | Gap for this athlete |
|---|---|---|
| Roxfit / Hyrox results | Official splits | No coaching, no plan |
| Runna | Running plans, Strava sync | No stations or strength; no public developer API |
| Box apps (e.g. the gym's WOD app) | Daily class programming | Not linked to his own plan |
| Strava | Activity log, public API | No programming |
| Spotify / Apple Music | Music | Not tied to session sections |

## Open questions

- Roxfit export or API: unknown; screenshots for v1, integration is a future R&D task.
- Apple distribution: the owner plans a free Apple Developer account, which allows only
  installs from Xcode on a Mac, lasting 7 days. The owner has a Mac (confirmed 23 Nov 2026).
- Music service: Spotify (needs Premium for a developer app) or Apple Music (needs the paid
  Apple account). Decided: future R&D, not in v1.
