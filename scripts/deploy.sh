#!/bin/sh
# Build and deploy Dumpit to Google Cloud Run (EU), from your own computer.
#
#   export DUMPIT_ALLOWED_EMAIL=you@example.com     # the one email that may sign in
#   export DUMPIT_MAIL_FROM=dumpit@yourdomain.com   # sender of the sign-in emails
#   sh scripts/deploy.sh staging                    # or: production
#
# Needs `gcloud auth login`, a project with billing (gcloud config set project <id>), and
# the secrets from scripts/setup-secrets.sh. Prints the service URL; record it with
#   pk ship record staging --url <url>
set -eu
cd "$(dirname "$0")/.."

ENV=${1:-}
case "$ENV" in
  staging)    SVC=dumpit-staging ;;
  production) SVC=dumpit ;;
  *) echo "usage: sh scripts/deploy.sh staging|production" >&2; exit 2 ;;
esac
: "${DUMPIT_ALLOWED_EMAIL:?export DUMPIT_ALLOWED_EMAIL=<the email that may sign in>}"
: "${DUMPIT_MAIL_FROM:?export DUMPIT_MAIL_FROM=<the sender address for sign-in emails>}"
PROJECT=${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}
[ -n "$PROJECT" ] || { echo "set a project: gcloud config set project <id>" >&2; exit 2; }
REGION=${DUMPIT_REGION:-europe-west1}

gcloud run deploy "$SVC" --source . --region "$REGION" --project "$PROJECT" \
  --allow-unauthenticated --min-instances 0 --max-instances 2 \
  --set-secrets "ANTHROPIC_API_KEY=$SVC-anthropic:latest,DUMPIT_DATABASE_URL=$SVC-database-url:latest,DUMPIT_SMTP_URL=$SVC-smtp-url:latest" \
  --set-env-vars "DUMPIT_ALLOWED_EMAIL=$DUMPIT_ALLOWED_EMAIL,DUMPIT_MAIL_FROM=$DUMPIT_MAIL_FROM" \
  --labels "commit=$(git rev-parse --short HEAD)"

URL=$(gcloud run services describe "$SVC" --region "$REGION" --project "$PROJECT" \
  --format 'value(status.url)')
echo
echo "Deployed $(git rev-parse --short HEAD) to $ENV: $URL"
echo "Record it:  pk ship record $ENV --url $URL"
