# Backlog: pankra

> From docs/spec.md and docs/acceptance.feature. Judge gate WAIVED (owner-reviewed spec);
> no panel ruling yet. Order is build order. A slice is done when its scenarios pass.

## Slice 1: Foundation
- **Delivers:** the web app and API run, the owner signs in, and CI is green on every push
- **Proposal phase:** 0
- **Scenarios:** the owner signs in with an email link; a sign-in link works only once; the API reports its health
- **Touches:** monorepo `api/` (Node 22, Fastify, TypeScript, Zod) and `app/` (Expo + Expo Router, web first); MongoDB connection and `migrations` collection with up/down scripts; single-owner auth (email magic link, `HttpOnly` `Secure` `SameSite=Lax` cookie, bearer token for iOS); `/api/v1` health route; shared types package; CI workflow running both test suites
- **Done when:** `npm test` passes in `api/` and `app/`; CI runs it; `pk qa -C .` still passes

## Slice 2: Week of whiteboard cards
- **Delivers:** Today and Week screens showing each session as a fully spelled-out card with status and results beside each day
- **Proposal phase:** 1
- **Scenarios:** a session shows as a fully spelled-out card
- **Touches:** `profiles`, `sessions` collections; `GET /sessions?from=&to=`; Today and Week screens
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 3: Add class and schedule shifter
- **Delivers:** adding a box class replaces the day's plan and pushes later sessions to the next free days, keeping the rest day
- **Proposal phase:** 1
- **Scenarios:** adding a class moves later sessions; a pushed session crosses into next week
- **Touches:** `POST /sessions/insert` (schedule-shifter), `status`/`movedFrom`/`source` on sessions; Add class screen (text input; screenshot input arrives with slice 8)
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 4: Key vault and retention
- **Delivers:** Claude and GPT keys entered in Settings, encrypted, shown as last 4 only, deleted on expiry or on request
- **Proposal phase:** 2
- **Scenarios:** expired key is deleted; a key is deleted on request
- **Touches:** `credentials`, `audit` collections; AES-256-GCM with master key from host secrets; `PUT`/`DELETE /credentials/:provider`; Agenda job every 15 minutes; Settings screen
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 5: Skill runner and provider adapters
- **Delivers:** a skill runs on Claude or GPT through one adapter interface, with every run logged and every failure leaving nothing half-saved
- **Proposal phase:** 2
- **Scenarios:** a skill runs on either provider; missing key blocks a run; provider failure leaves no partial result; invalid model output is not saved; cost cap stops runs
- **Touches:** `ProviderAdapter` (Anthropic Messages API, OpenAI Responses API, images and tools); skill runner (prompt build, output-schema validation with one repair attempt); `runs` collection; `POST /runs`, `GET /runs/:id`; monthly cost cap per provider
- **Done when:** its scenarios pass as automated tests (providers faked at the HTTP boundary); `pk qa -C .` still passes

## Slice 6: Registry sync
- **Delivers:** the app pulls skills, agents and plugins from project-kit's `registry/` by itself, versioned, and survives a bad or missing registry
- **Proposal phase:** 3
- **Scenarios:** the app pulls the registry by itself; registry offline keeps current skills; invalid registry node is skipped
- **Touches:** `nodes`, `edges` collections (unique on kind + name + version, `retired` flag); `REGISTRY_REPO`/`REGISTRY_REF` config; `POST /registry/sync`; Agenda job every 6 hours
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 7: Skills graph
- **Delivers:** every skill, agent, plugin and provider as an interactive graph; hover lights an agent's steps in order, click opens its run panel
- **Proposal phase:** 3
- **Scenarios:** hovering an agent shows its run order; clicking a node opens its run panel
- **Touches:** `GET /nodes`, `GET /edges`; Skills screen with Cytoscape.js (WebView on iOS), styling after Project Kit's graph viewer; run panel wired to slice 5's runner and slice 4's credential status
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 8: Log results and read screenshots
- **Delivers:** results typed or read from screenshots, confirmed before saving, with feedback against the plan
- **Proposal phase:** 4
- **Scenarios:** a result gets feedback against the plan; screenshot values need confirmation
- **Touches:** `results`, `uploads` collections; R2 private bucket with 10-minute signed URLs; `POST /results`, `POST /uploads`, `POST /uploads/:id/confirm`; Log screen; screenshot input for Add class
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 9: Races, paces and Strava
- **Delivers:** Hyrox race breakdown by seconds to gain per segment, pace targets per machine, and Strava runs arriving by webhook
- **Proposal phase:** 4
- **Scenarios:** a race is broken down by seconds to gain; duplicate Strava event imports once
- **Touches:** `races` collection; `GET /races`, `GET /races/:id/analysis`; Strava OAuth (token in key vault), `POST /webhooks/strava` idempotent on activity id, backfill job; Races and Paces screens
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 10: Fuel and share
- **Delivers:** meals before and after from a fridge photo, a race-morning plan, and the day's workout exported as a 1080 × 1350 Instagram PNG
- **Proposal phase:** 5
- **Scenarios:** meals are suggested from a fridge photo; the day's workout exports as an Instagram image
- **Touches:** Fuel screen using the skill runner with an image; Share screen rendering the day's card to PNG
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 11: iPhone app
- **Delivers:** the app installs from Xcode on the owner's iPhone and shows the same week as the web app
- **Proposal phase:** 6
- **Scenarios:** reinstalled iPhone app shows the same week
- **Touches:** `app.json` (bundle ID from docs/inputs-checklist.md, free capabilities only); `npx expo prebuild -p ios` with `ios/` committed; `scripts/install-ios.sh`; `docs/ios-install.md`; production API URL
- **Done when:** its scenarios pass as automated tests (data restored from the server after reinstall); `pk qa -C .` still passes
