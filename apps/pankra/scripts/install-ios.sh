#!/usr/bin/env bash
# Install PANKRA on your iPhone from this Mac with a free Apple account (Personal Team).
# Run it the first time and again every 7 days, when the free signing expires:
#
#   PANKRA_BUNDLE_ID=com.yourname.pankra PANKRA_API_URL=https://<your-api>/api/v1 ./scripts/install-ios.sh
#
# Your data lives on the server, so a reinstall brings back the same weeks once you sign in.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() { echo "install-ios: $*" >&2; exit 1; }

[[ "$(uname)" == "Darwin" ]] || fail "this needs a Mac with Xcode"
command -v xcodebuild >/dev/null || fail "install Xcode from the Mac App Store and open it once"
command -v pod >/dev/null || fail "install CocoaPods: brew install cocoapods"
command -v node >/dev/null || fail "install Node 22: brew install node"
[[ -n "${PANKRA_BUNDLE_ID:-}" ]] || fail "set PANKRA_BUNDLE_ID, e.g. com.yourname.pankra"
[[ -n "${PANKRA_API_URL:-}" ]] || fail "set PANKRA_API_URL, e.g. https://pankra-api.onrender.com/api/v1"
[[ "$PANKRA_API_URL" == https://* ]] || fail "PANKRA_API_URL must be https:// (iOS refuses plain http)"

cd "$here"
npm ci

cd "$here/app"
# Regenerate the native project when it is missing or was made for another bundle ID.
if [[ ! -d ios ]] || ! grep -q "$PANKRA_BUNDLE_ID" ios/*.xcodeproj/project.pbxproj 2>/dev/null; then
  npx expo prebuild --platform ios --clean
fi
(cd ios && pod install)

echo
echo "Connect the iPhone by cable and unlock it. The first time only: in Xcode, open"
echo "app/ios/PANKRA.xcworkspace > PANKRA target > Signing & Capabilities > Team = your Personal Team."
echo
npx expo run:ios --device --configuration Release
