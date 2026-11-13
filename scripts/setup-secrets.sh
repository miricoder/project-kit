#!/bin/sh
# Store Dumpit's secrets in Google Secret Manager for one environment. Run on your own
# computer after `gcloud auth login`. Each value is typed at a hidden prompt and goes
# straight to Secret Manager: never into a file, the repo or your shell history.
#
#   sh scripts/setup-secrets.sh staging
#   sh scripts/setup-secrets.sh production
#
# Staging and production get separate secrets (and should get separate databases).
set -eu

ENV=${1:-}
case "$ENV" in
  staging)    SVC=dumpit-staging ;;
  production) SVC=dumpit ;;
  *) echo "usage: sh scripts/setup-secrets.sh staging|production" >&2; exit 2 ;;
esac
PROJECT=${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}
[ -n "$PROJECT" ] || { echo "set a project: gcloud config set project <id>" >&2; exit 2; }

gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  secretmanager.googleapis.com artifactregistry.googleapis.com --project "$PROJECT"

# Cloud Run runs as the project's default compute service account; let it read secrets.
NUMBER=$(gcloud projects describe "$PROJECT" --format 'value(projectNumber)')
gcloud projects add-iam-policy-binding "$PROJECT" --condition=None --quiet \
  --member "serviceAccount:${NUMBER}-compute@developer.gserviceaccount.com" \
  --role roles/secretmanager.secretAccessor >/dev/null

store() {  # store <secret-name> <what to type>
  printf '%s: ' "$2"
  stty -echo 2>/dev/null || true
  IFS= read -r VALUE
  stty echo 2>/dev/null || true
  echo
  [ -n "$VALUE" ] || { echo "  skipped (empty)"; return; }
  if gcloud secrets describe "$1" --project "$PROJECT" >/dev/null 2>&1; then
    printf %s "$VALUE" | gcloud secrets versions add "$1" --data-file=- --project "$PROJECT" >/dev/null
  else
    printf %s "$VALUE" | gcloud secrets create "$1" --data-file=- --project "$PROJECT" >/dev/null
  fi
  VALUE=
  echo "  stored $1"
}

echo "Secrets for $ENV ($SVC) in project $PROJECT. Typing is hidden; leave empty to skip."
store "$SVC-anthropic"    "Anthropic API key (console.anthropic.com)"
store "$SVC-database-url" "Postgres URL (postgresql://user:password@host/db?sslmode=require)"
store "$SVC-smtp-url"     "SMTP URL for sign-in emails (smtps://user:password@host:465)"
echo "Done. Deploy with: sh scripts/deploy.sh $ENV"
