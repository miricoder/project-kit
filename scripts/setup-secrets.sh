#!/bin/sh
# Store Dumpit's settings in Google Secret Manager for one environment. Run in Google Cloud
# Shell (or anywhere after `gcloud auth login`). Each value is typed at a hidden prompt and goes
# straight to Secret Manager: never into a file, the repo or your shell history. Run it again
# to change a value.
#
#   sh scripts/setup-secrets.sh staging
#   sh scripts/setup-secrets.sh production
set -eu

ENV=${1:-}
case "$ENV" in
  staging)    SVC=dumpit-staging ;;
  production) SVC=dumpit ;;
  *) echo "usage: sh scripts/setup-secrets.sh staging|production" >&2; exit 2 ;;
esac
PROJECT=${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}
[ -n "$PROJECT" ] || { echo "set a project: gcloud config set project <id>" >&2; exit 2; }

store() {  # store <secret-name> <what to type>
  printf '%s: ' "$2"
  stty -echo 2>/dev/null || true
  IFS= read -r VALUE
  stty echo 2>/dev/null || true
  echo
  if [ -z "$VALUE" ]; then
    gcloud secrets describe "$1" --project "$PROJECT" >/dev/null 2>&1 \
      && echo "  kept the stored value" || echo "  skipped: the deploy needs this one"
    return
  fi
  if gcloud secrets describe "$1" --project "$PROJECT" >/dev/null 2>&1; then
    printf %s "$VALUE" | gcloud secrets versions add "$1" --data-file=- --project "$PROJECT" >/dev/null
  else
    printf %s "$VALUE" | gcloud secrets create "$1" --data-file=- --project "$PROJECT" >/dev/null
  fi
  VALUE=
  echo "  stored"
}

echo "Settings for $ENV in project $PROJECT. Typing is hidden; press Enter to keep a stored value."
store "$SVC-anthropic"       "Anthropic API key"
store "$SVC-database-url"    "Postgres connection string (postgresql://...)"
store "$SVC-smtp-url"        "Email sending (smtps://YOU%40gmail.com:APP-PASSWORD@smtp.gmail.com:465)"
store "$SVC-mail-from"       "Sender address for sign-in emails"
store "$SVC-allowed-email"   "The email that may sign in"
echo "Done."
