# Installing PANKRA on your iPhone (free Apple account)

The free Apple account cannot publish an app: there is no TestFlight and no App Store. PANKRA
is installed from Xcode on your Mac, and stops opening **7 days** after each install until
you run the install again. Your training data is on the server, so a reinstall shows the
same weeks, results and races as soon as you sign in.

## What you need

| Item | Where it comes from |
|---|---|
| A Mac with Xcode | Mac App Store; open Xcode once after installing |
| Your Apple Account | Signed in to Xcode (Settings > Accounts); the password is never given to anyone else |
| A bundle ID | Your choice, e.g. `com.yourname.pankra`: reverse-domain, letters, digits, dots |
| The API address | From the deploy step, e.g. `https://pankra-api.onrender.com/api/v1` |
| Your iPhone and a cable | Developer Mode on (Settings > Privacy & Security > Developer Mode, then restart) |

## Once

1. Sign in at developer.apple.com with your Apple Account and accept the agreement.
2. On the Mac: `brew install node watchman cocoapods`.
3. Xcode > Settings > Accounts: add your Apple Account. A *Personal Team* appears.
4. Connect the iPhone by cable and tap **Trust**.

## Install (first time, then every 7 days)

```bash
git pull
PANKRA_BUNDLE_ID=com.yourname.pankra PANKRA_API_URL=https://<your-api>/api/v1 apps/pankra/scripts/install-ios.sh
```

The first time only:

- In Xcode, open `apps/pankra/app/ios/PANKRA.xcworkspace`, select the **PANKRA** target,
  **Signing & Capabilities**, and set **Team** to your Personal Team. Run the script again.
- On the iPhone: Settings > General > VPN & Device Management > your developer profile >
  **Trust**.

Then open PANKRA, enter your email, and open the sign-in link from the email **on the
iPhone**: it opens the app and signs you in.

## If something goes wrong

| What you see | What to do |
|---|---|
| "Untrusted Developer" | Trust the profile (VPN & Device Management) |
| The app opens and closes at once | The 7 days are up: run the install again |
| "Signing requires a development team" | Set Team to your Personal Team in Xcode |
| "Failed to register bundle identifier" | That ID is taken: choose another `PANKRA_BUNDLE_ID` |
| More than 3 apps | A free account allows 3 such apps per iPhone: delete one |

## Rolling back

Check out the previous release tag and run the install script again:
`git checkout v<previous> && apps/pankra/scripts/install-ios.sh`.

With the paid Apple Developer Program ($99 a year) the same app can go to TestFlight and
the 7-day limit goes away (see docs/spec.md, iOS deployment).
