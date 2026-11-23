# Backlog: pankra

> From docs/spec.md and docs/acceptance.feature, judge gate WAIVED by the owner (design
> approved directly, 2026-11-23). Order is build order. A slice is done when its scenarios pass.

## Slice 1: Foundation and the Today card
- **Delivers:** the TypeScript workspace (API, app, shared types), the sessions API and the Today screen showing a session as a fully spelled-out whiteboard card
- **Proposal phase:** 0, 1
- **Scenarios:** a session shows as a fully spelled-out card
- **Touches:** API (Fastify, `GET /api/v1/sessions`), data model (Profile, Session), app Today screen, shared card formatter
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 2: Add class and the schedule shifter
- **Delivers:** adding a box class to a day replaces its plan and pushes later sessions to the next free days, keeping the rest day, across week boundaries
- **Proposal phase:** 1
- **Scenarios:** adding a class moves later sessions; a pushed session crosses into next week
- **Touches:** `POST /api/v1/sessions/insert`, Session (status, movedFrom, source), Profile (restDay), app Add class and Week screens
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 3: Key vault and retention
- **Delivers:** Claude and GPT keys saved encrypted with a chosen retention, shown as last4, deleted on expiry or on request, audited
- **Proposal phase:** 2
- **Scenarios:** expired key is deleted; a key is deleted on request
- **Touches:** key vault (AES-256-GCM), Credential, Audit, `PUT/DELETE /api/v1/credentials/:provider`, expiry job, node credential badge, app Settings
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 4: Skill runner and provider adapters
- **Delivers:** a skill runs on Claude or GPT through one adapter interface, with every run saved, and refused or failed cleanly on a missing key, provider error, invalid output or the monthly cap
- **Proposal phase:** 2
- **Scenarios:** a skill runs on either provider; missing key blocks a run; provider failure leaves no partial result; invalid model output is not saved; cost cap stops runs
- **Touches:** skill runner, ProviderAdapter (Anthropic Messages, OpenAI Responses), Run, `POST/GET /api/v1/runs`, key vault, run panel
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 5: Log results with feedback
- **Delivers:** results typed against a session, analysed by result-analyzer into feedback with tips
- **Proposal phase:** 2
- **Scenarios:** a result gets feedback against the plan
- **Touches:** `POST /api/v1/results`, Result, result-analyzer output schema, app Log screen
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 6: Registry sync
- **Delivers:** the API pulls skills, agents and plugins from project-kit's `registry/` at `REGISTRY_REF` by itself, versioned, tolerant of outages and bad nodes
- **Proposal phase:** 3
- **Scenarios:** the app pulls the registry by itself; registry offline keeps current skills; invalid registry node is skipped
- **Touches:** registry sync, Node, Edge, Audit, `POST /api/v1/registry/sync`, `GET /api/v1/nodes`, `GET /api/v1/edges`, 6-hourly job, Settings last sync time
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 7: Skills graph screen
- **Delivers:** the interactive Cytoscape graph of every node: hover lights an agent's steps in order, click opens the run panel
- **Proposal phase:** 3
- **Scenarios:** hovering an agent shows its run order; clicking a node opens its run panel
- **Touches:** app Skills screen (Cytoscape.js), nodes and edges API, run panel, credential badge
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 8: Data in: screenshots, races and Strava
- **Delivers:** Hyrox screenshots become confirmed race splits, races are broken down by seconds to gain, and Strava runs import once by webhook
- **Proposal phase:** 4
- **Scenarios:** screenshot values need confirmation; a race is broken down by seconds to gain; duplicate Strava event imports once
- **Touches:** `POST /api/v1/uploads`, `POST /api/v1/uploads/:id/confirm`, Upload, Race, `GET /api/v1/races/:id/analysis`, `POST /api/v1/webhooks/strava`, Strava OAuth, object storage, app Races and Paces screens
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes

## Slice 9: Fuel and share
- **Delivers:** meals before and after a session from a fridge photo, a race-morning plan, and the day's workout exported as a 1080 × 1350 Instagram PNG
- **Proposal phase:** 5
- **Scenarios:** none in docs/acceptance.feature (proposal phase 5 has no Gherkin; tested by unit tests only)
- **Touches:** skill runner (fuel skill, vision input), uploads, app Fuel and Share screens, image export
- **Done when:** its unit tests pass; `pk qa -C .` still passes

## Slice 10: iPhone app
- **Delivers:** the Expo app prebuilt for iOS, installed from Xcode with the free Personal Team, showing the same week as the web app after a reinstall
- **Proposal phase:** 6
- **Scenarios:** reinstalled iPhone app shows the same week
- **Touches:** `app.json` (bundle ID, free capabilities only), `ios/`, `scripts/install-ios.sh`, `docs/ios-install.md`, bearer-token auth, Week screen
- **Done when:** its scenarios pass as automated tests; `pk qa -C .` still passes
