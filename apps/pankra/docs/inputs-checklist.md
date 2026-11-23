# What the owner provides before PANKRA can deploy

Project Kit writes, builds and tests everything without these. It stops at the matching
deploy step until each item is in place. **Never paste a secret into chat or commit it.**
Each secret goes where the last column says.

| # | Item | Needed for | Where you get it | How you hand it over | Status |
|---|---|---|---|---|---|
| 1 | A Mac with Xcode | iPhone install | Your Mac (confirmed) | You run the install script | ☑ Mac confirmed; Xcode to install |
| 2 | Apple Account email | Signing as a Personal Team | appleid.apple.com | Sign in to Xcode yourself; the password is never needed | ☐ |
| 3 | Bundle ID | iPhone app identity | Your choice, e.g. `com.yourname.pankra` | Tell Project Kit | ☐ |
| 4 | GitHub repo for the app | Code, CI | `gh repo create <you>/pankra --private` | Give the session push access | ☐ |
| 5 | MongoDB Atlas cluster + connection string | Database | cloud.mongodb.com (free M0) | API host secret `MONGODB_URI` | ☐ |
| 6 | Vercel account, repo connected | Web hosting | vercel.com | Connect the repo in Vercel | ☐ |
| 7 | Render or Fly.io account, repo connected | API hosting | render.com / fly.io | Add secrets in the host's dashboard | ☐ |
| 8 | Cloudflare R2 bucket + access keys | Images | dash.cloudflare.com | API host secrets `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | ☐ |
| 9 | Vault master key | Encrypting user keys | Project Kit generates it (`openssl rand -base64 32`) | API host secret `VAULT_KEY` only | ☐ |
| 10 | Strava API application | Run sync | strava.com/settings/api | API host secrets `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`; callback URL from Project Kit | ☐ |
| 11 | Anthropic and OpenAI API keys | Skills inside PANKRA | console.anthropic.com, platform.openai.com | Typed into PANKRA Settings, with a retention choice | ☐ |
| 12 | Monthly LLM cost cap per provider | Cost control | Your choice, e.g. $10 each | PANKRA Settings | ☐ |
| 13 | Three judge keys from non-Anthropic model families | Project Kit's judge gate before build | Provider consoles | `pk keys add <family>` on the machine running Project Kit | ☐ |
| 14 | `REGISTRY_REF` | Which registry version the app runs | A tag on miricoder/project-kit, after the registry PR merges | API host env var | ☐ |

## Later, with the paid Apple account ($99 a year)

| Item | Needed for | How you hand it over |
|---|---|---|
| Apple Developer Program membership | TestFlight, App Store, MusicKit, push | Enrol at developer.apple.com |
| App Store Connect app record (same bundle ID) | Submitting builds | Create in App Store Connect |
| App Store Connect API key: Issuer ID, Key ID, `.p8` file | EAS build and submit | Expo EAS secrets, never chat |
| Expo account | EAS cloud builds | `eas login` on your machine |
