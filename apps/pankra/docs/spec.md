# Technical spec: PANKRA

> Phase 3 of the Project Kit pipeline. Bound by the v1 cut and out-of-scope list in
> docs/proposal.md. Acceptance criteria live in docs/acceptance.feature.

## Architecture

```
  iPhone app (Expo, installed from Xcode)        Web app (Expo web, Vercel)
                 \                                   /
                  \__________ HTTPS + JSON _________/
                                   |
  +--------------------------------v---------------------------------------+
  | API  Node.js 22 + Fastify + TypeScript                                 |
  |                                                                        |
  |  Training API      Skill runner        Provider adapters    Key vault  |
  |  profile, sessions runs skills/agents  Claude | GPT         AES-GCM    |
  |  results, races    logs every run      (Llama later)        retention  |
  |                                                                        |
  |  Registry sync     Strava sync         Jobs                             |
  |  pulls registry/   OAuth + webhook     Agenda                           |
  +-----|---------------|------------------|---------------------|---------+
        |               |                  |                     |
   GitHub raw      Strava API                             MongoDB Atlas
   (project-kit)                                           + R2/S3 images
```

| Component | Owns | Depends on |
|---|---|---|
| App (iOS + web) | Screens: Today, Week, Add class, Log, Races, Paces, Fuel, Share, Skills, Settings | API |
| Training API | Profile, sessions, results, races, uploads | MongoDB, object storage |
| Skill runner | Running a skill or agent: build the prompt, call the adapter, validate output, save the run | Registry nodes, adapters, key vault |
| Provider adapters | One interface over Anthropic Messages API and OpenAI Responses API, incl. images and tool calls | Provider HTTPS APIs |
| Key vault | Encrypting, storing, expiring and deleting user keys and tokens | Master key in host secrets |
| Registry sync | Pulling `registry/index.json` and changed nodes from project-kit | GitHub raw content |
| Strava sync | OAuth, webhook, activity import | Strava API |
| Jobs | Key expiry, registry sync every 6 h, Strava backfill | Agenda on MongoDB |

## Decisions

| Decision | Chosen | Rejected | Why |
|---|---|---|---|
| App framework | Expo (React Native) + Expo Router | SwiftUI + separate web app; Flutter | One TypeScript codebase for iPhone and web; free Xcode install works with Expo prebuild |
| API | Node.js + Fastify + Zod | Python FastAPI | Types shared with the app; one language |
| Database | MongoDB Atlas (owner's choice) | Postgres | Session shapes vary (class, track, gym); owner asked for Mongo |
| Graph view | Cytoscape.js (WebView on iOS) | Neo4j database; react-force-graph | Look of Neo4j Browser without running a graph database; stores graph as edges in Mongo |
| LLM access | Provider adapter, user's own keys | One vendor SDK only | Owner wants Claude and GPT, and any later provider |
| Skills storage | project-kit `registry/` pulled at runtime, versioned copy in Mongo | Skills only in the app's DB; skills baked into the build | Owner wants Project Kit to create and manage them; versions make runs repeatable |
| Music | Future R&D, out of v1 | Spotify App Remote in v1 | Owner's call: service not chosen; Spotify needs Premium, Apple MusicKit needs the paid Apple account |
| iPhone distribution (v1) | Free Personal Team, install from Xcode | TestFlight, App Store | Owner chose the free account; TestFlight needs the paid one |
| Hosting | Vercel (web), Render or Fly.io (API) | One VPS | Free tiers, managed https, preview deploys |
| Images | Cloudflare R2 (S3 API) | Images in Mongo | Size and cost |

**Reused from existing work:** the owner's chat workflow (skills now in
`registry/skills/`), and Project Kit's own graph viewer pattern (`skills/graph/viewer.html`)
for node and edge styling.

## Data model

Every document has `userId`, `schemaVersion`, `createdAt`, `updatedAt`.

| Entity | Fields | Lives in |
|---|---|---|
| Profile | division, goals, raceCalendar, equipment, matLengthM (12.5), restDay, units, paces per machine, strength baselines | `profiles` |
| Session | date, title, type (gym, track, class, rest), tag, sections[{kind, label, lines}], notes, log, status (Done, Today, Scheduled, Moved, Skipped), movedFrom, source (plan, class) | `sessions` |
| Result | sessionId, parts[{label, loadKg, reps, timeS, distanceM, speedKmh, rpe}], notes, uploadIds | `results` |
| Race | event, date, division, totalS, runs[8], stations[8], roxzoneS, ranks, lapsPerKm | `races` |
| Upload | storageKey, mime, kind, extracted, confirmed | `uploads` |
| Node | kind, name, version, description, files (text), providers, requires, vision, tools, input, output, steps, skills, agents, retired | `nodes` (unique on kind + name + version) |
| Edge | from, to, type (contains, calls, uses, runsOn), order | `edges` |
| Credential | provider (claude, gpt, strava), ciphertext, iv, last4, retention, expiresAt | `credentials` |
| Run | nodeRef (kind, name, version), provider, model, inputRef, output, tokens, costUsd, status, error | `runs` |
| Audit | action (keyAdded, keyDeleted, retentionChanged, registrySynced), at, detail | `audit` |

- **Schema versioning:** `schemaVersion` on every document; migrations are numbered scripts
  in `api/migrations/`, run on deploy, recorded in a `migrations` collection.
- **Migration:** forward scripts; **reverse:** every migration ships a `down` that restores
  the previous shape. Migrations that drop data are refused unless they copy it to a
  `<collection>_archive` first.

## Interfaces

REST, JSON, all under `/api/v1`, authenticated with a session cookie (web) or bearer token
(iOS).

```
GET    /sessions?from=&to=            -> Session[]
POST   /sessions/insert               {date, session}          -> {changes[]}  (schedule-shifter)
POST   /results                       {sessionId, parts[]}     -> Result
POST   /uploads                       multipart image          -> Upload (extracted, unconfirmed)
POST   /uploads/:id/confirm           {data}                   -> Upload
GET    /races  /races/:id/analysis
GET    /nodes  /edges                                         (the graph)
POST   /runs                          {node, provider, model, input, uploadIds} -> Run
GET    /runs/:id
PUT    /credentials/:provider         {secret, retention}      -> {last4, expiresAt}
DELETE /credentials/:provider                                  -> 204
POST   /registry/sync                                          -> {added, updated, retired}
POST   /webhooks/strava
```

Provider adapter, inside the API:

```ts
interface ProviderAdapter {
  id: 'claude' | 'gpt';
  run(req: {system: string; input: unknown; images: Buffer[]; tools: ToolDef[];
            outputSchema: JSONSchema; model: string; apiKey: string}): Promise<{
    output: unknown; tokensIn: number; tokensOut: number; costUsd: number }>;
}
```

### Registry sync

1. Config: `REGISTRY_REPO=miricoder/project-kit`, `REGISTRY_REF` (a tag for releases).
2. Fetch `https://raw.githubusercontent.com/<repo>/<ref>/registry/index.json`.
3. For each node whose `version` is new, fetch its files, validate `node.json`, insert as a
   new `nodes` version; replace `edges` from the index.
4. A node no longer in the index is marked `retired`, never deleted.
5. Runs reference `name + version`, so a past run can be shown and repeated exactly.

### Keys and retention

- AES-256-GCM, 96-bit random IV per secret, master key from the API host's secrets.
- Retention choices: this session, 24 hours, 7 days, 30 days, until deleted.
- An Agenda job every 15 minutes deletes expired credentials and writes an audit entry.
- Keys never leave the API after saving; the app sees `last4` only. Keys are never logged and
  never stored in `runs`.

### Skills graph

Cytoscape.js force layout. Node shapes: skill (circle), agent (large circle), plugin
(double ring), provider (box). Edges: contains, calls (numbered by order), uses, runsOn
(dashed). Hover highlights the node and neighbours and numbers an agent's steps. Click opens
a run panel: description, input form (text, images), provider and model, credential status,
Run, last 5 runs. Badge green when the chosen provider has what the node `requires`, amber
when not.

### Music (future R&D)

Not in v1. The registry holds a draft `music-curator` skill (tempo band per section,
running cadence, timer ducking). Before it is built: choose the service. Spotify needs the
owner on Spotify Premium for a Development Mode app; Apple Music (MusicKit) needs the paid
Apple Developer Program.

## Failure modes

| What goes wrong | System does | Scenario |
|---|---|---|
| No key for the chosen provider | Blocks the run before any call; run panel asks for the key | missing key blocks a run |
| Key past its retention | Job deletes it, audits it; node badge turns amber | expired key is deleted |
| Provider returns an error or times out | Run marked failed with the provider's message; no partial output saved; Retry offered | provider failure leaves no partial result |
| Output fails the node's output schema | One automatic repair attempt, then failed; nothing written | invalid model output is not saved |
| Monthly cost cap reached | Runs refused until next month or cap raised | cost cap stops runs |
| Registry unreachable | Keeps current nodes; shows last sync time; retries next cycle | registry offline keeps current skills |
| Registry node invalid | That node skipped and reported; others load | invalid registry node is skipped |
| Screenshot misread | Values shown for confirmation; uncertain fields marked; nothing saved until confirmed | screenshot values need confirmation |
| Class added on a day with a session | Later sessions move; rest day kept; heavy back-to-back flagged | adding a class moves later sessions |
| Push past end of week | Session goes to next week, reported | a pushed session crosses into next week |
| Strava webhook duplicate | Idempotent on activity id | duplicate Strava event imports once |
| iPhone app expired (7 days) | Data safe on server; reinstall from Xcode restores it | reinstalled iPhone app shows the same week |

## Rollback

| Layer | How | Tested by |
|---|---|---|
| Code | Redeploy the previous release tag on Vercel and Render (both keep prior builds) | `/launch` rollback drill via `pk ship` |
| Data | Reverse migration (`down`) for the release's migrations; archive collections for any dropped data | Migration tests run up then down on a seeded DB |
| Registry | Set `REGISTRY_REF` to the previous tag and sync; old node versions are still in Mongo | registry offline keeps current skills |
| iPhone | Reinstall the previous tag from Xcode | Manual, documented in `docs/ios-install.md` |

## Security and privacy

| Concern | Handling |
|---|---|
| Sensitive data | Health and training data, photos: private bucket, signed URLs (10 min), one user |
| Secrets | LLM keys and OAuth tokens in the key vault; infrastructure secrets only in host secret stores; secret scan in CI (`pk ship audit`) |
| What gets logged | Request ids, node names, providers, token counts, durations; never keys, never prompt images, never full outputs outside `runs` |
| Auth | Single owner account; passkey or email magic link; session cookie `HttpOnly`, `Secure`, `SameSite=Lax` |
| Prompt injection from images or registry text | Registry text and extracted text are data; tools a node may call are limited to its `tools` list; writes need user confirmation |

## iOS deployment (free Apple Developer account)

The free account cannot distribute an app: there is no download area, no TestFlight and no
App Store. The app is installed from Xcode on a Mac to the owner's iPhone, and stops opening
7 days after install until reinstalled. At most 3 such apps per device; no push, iCloud,
Sign in with Apple or MusicKit.

**Owner, once:**

1. Sign in at developer.apple.com with the Apple Account and accept the developer agreement.
2. On the Mac: Xcode from the Mac App Store (open once), then
   `brew install node watchman cocoapods`.
3. Xcode > Settings > Accounts: add the Apple Account; a Personal Team appears.
4. iPhone: Settings > Privacy & Security > Developer Mode on; restart.
5. Connect by cable; tap Trust.

**Project Kit:**

1. Bundle ID `com.<owner>.pankra` (from `docs/inputs-checklist.md`); only free capabilities
   in `app.json`.
2. `npx expo prebuild -p ios`; commit `ios/`.
3. Commit `scripts/install-ios.sh` (`npm ci`, `npx pod-install`,
   `npx expo run:ios --device --configuration Release`) and `docs/ios-install.md`.
4. Point the iOS build at the production API URL.

**Owner, first install and every 7 days:** `git pull && ./scripts/install-ios.sh`; first
time only, Xcode > PANKRA target > Signing & Capabilities > Team = Personal Team, then on the
iPhone Settings > General > VPN & Device Management > trust the developer profile.

The owner has a Mac (confirmed). Without one, the web app added to the Home Screen would be
the iPhone app until the paid account.

**Paid account later ($99/year):** enrol; App Store Connect app record (same bundle ID);
App Store Connect API key (Issuer ID, Key ID, .p8) stored in Expo EAS secrets;
`eas build -p ios` and `eas submit` to TestFlight; enable MusicKit, push, Sign in with Apple.

## Not built

Session music (future R&D; registry skill `music-curator` is drafted), other users and
coaches, Android, App Store and TestFlight, push, Sign in with
Apple, Roxfit or Hyrox API integration, other LLM providers, payments, social features,
wearables beyond Strava.

## Strongest counter-argument

The free Apple path may sink the iPhone half of v1. A 7-day reinstall from a Mac is the kind
of chore people stop doing within a month, even with a Mac to hand. If he stops, the native
app delivers nothing the web app does not. A design that treated the web app as
the only v1 client and bought the $99 account before building native would ship sooner,
with less to maintain, and lose only features the owner might never install. The registry
adds a second risk: pulling instructions at runtime from a public repository means a bad
merge to `main` changes the live app; pinning `REGISTRY_REF` to a tag is the only guard, and
it depends on discipline.
