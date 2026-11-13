#!/bin/sh
# Every test Dumpit has: Python (service, Validator, eval; needs Postgres binaries or
# DUMPIT_TEST_DATABASE_URL), the web app's unit tests, and the browser tests against a
# built app and a throwaway server. This is the command `pk slice done` runs.
set -eu
cd "$(dirname "$0")/.."
# The test build is version 0.2.0, to match tests/fixtures/changelog.md (slice 15).
export APP_VERSION="${TEST_APP_VERSION:-0.2.0}"
python3 -m pytest -q
cd web
[ -d node_modules ] || npm ci --no-audit --no-fund
npm run build --silent
npx vitest run
node --test --test-concurrency=1 e2e/*.test.cjs
