# What the owner provides, and when

## Before `/handover` (nothing can be built without these)

| Item | Why | How you hand it over | Status |
|---|---|---|---|
| Empty private GitHub repo for the app, e.g. `miricoder/pankra` | `pk` refuses to run inside project-kit; pipeline state and code live here | Create it on GitHub; tell the session its name so it can attach it | ☐ |
| At least one judge key from a non-Anthropic provider | The judge panel (three families) must rule before `/initiate` can write the backlog `/build` needs | `pk keys add <family>` on the machine running Project Kit; other seats can be paste seats | ☐ |

## Before deploy steps

Project Kit writes, builds and tests everything without these. It stops at the matching
deploy step until each item is in place. **Never paste a secret into chat or commit it.**
Each secret goes where the last column says.

| # | Item | Needed for | Where you get it | How you hand it over | Status |
|---|---|---|---|---|---|
| 1 | A Mac with Xcode | iPhone install | Your Mac (confirmed) | You run the install script | ☑ Mac confirmed; Xcode to install |
| 2 | Apple Account email | Signing as a Personal Team | appleid.apple.com | Sign in to Xcode yourself; the password is never needed | ☐ |
| 3 | Bundle ID | iPhone app identity | Your choice, e.g. `com.yourname.pankra` | Tell Project Kit | ☐ |
| 4 | MongoDB Atlas cluster + connection string | Database | cloud.mongodb.com (free M0) | API host secret `MONGODB_URI` | ☐ |
| 5 | Vercel account, repo connected | Web hosting | vercel.com | Connect the repo in Vercel | ☐ |
| 6 | Render or Fly.io account, repo connected | API hosting | render.com / fly.io | Add secrets in the host's dashboard | ☐ |
| 7 | Cloudflare R2 bucket + access keys | Images | dash.cloudflare.com | API host secrets `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | ☐ |
| 8 | Vault master key | Encrypting user keys | Project Kit generates it (`openssl rand -base64 32`) | API host secret `VAULT_KEY` only | ☐ |
| 9 | Strava API application | Run sync | strava.com/settings/api | API host secrets `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`; callback URL from Project Kit | ☐ |
| 10 | Anthropic and OpenAI API keys | Skills inside PANKRA | console.anthropic.com, platform.openai.com | Typed into PANKRA Settings, with a retention choice | ☐ |
| 11 | Monthly LLM cost cap per provider | Cost control | Your choice, e.g. $10 each | PANKRA Settings | ☐ |
| 12 | `REGISTRY_REF` | Which registry version the app runs | A tag on miricoder/project-kit, after the registry PR merges | API host env var | ☐ |

## Later, with the paid Apple account ($99 a year)

| Item | Needed for | How you hand it over |
|---|---|---|
| Apple Developer Program membership | TestFlight, App Store, MusicKit, push | Enrol at developer.apple.com |
| App Store Connect app record (same bundle ID) | Submitting builds | Create in App Store Connect |
| App Store Connect API key: Issuer ID, Key ID, `.p8` file | EAS build and submit | Expo EAS secrets, never chat |
| Expo account | EAS cloud builds | `eas login` on your machine |
