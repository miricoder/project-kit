#!/bin/sh
# Build Dumpit's image and deploy it to Google Cloud Run (europe-west1).
#
#   sh scripts/deploy.sh staging        # or: production
#
# CI runs this after the tests pass (staging on every push; production on a v* tag, after
# approval). By hand, run it in Google Cloud Shell, which has gcloud and Docker built in.
# Needs scripts/setup-cloud.sh (once) and scripts/setup-secrets.sh (once per environment).
set -eu
cd "$(dirname "$0")/.."

ENV=${1:-}
case "$ENV" in
  staging)    SVC=dumpit-staging ;;
  production) SVC=dumpit ;;
  *) echo "usage: sh scripts/deploy.sh staging|production" >&2; exit 2 ;;
esac
PROJECT=${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}
[ -n "$PROJECT" ] || { echo "set a project: gcloud config set project <id>" >&2; exit 2; }
REGION=${GCP_REGION:-europe-west1}
VERSION=$(sh scripts/version.sh)
IMAGE="$REGION-docker.pkg.dev/$PROJECT/dumpit/dumpit:$(git rev-parse --short HEAD)"

echo "Building $VERSION for $ENV"
gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet
docker build --build-arg APP_VERSION="$VERSION" -t "$IMAGE" .
docker push "$IMAGE"

SECRETS="ANTHROPIC_API_KEY=$SVC-anthropic:latest"
SECRETS="$SECRETS,DUMPIT_DATABASE_URL=$SVC-database-url:latest"
SECRETS="$SECRETS,DUMPIT_SMTP_URL=$SVC-smtp-url:latest"
SECRETS="$SECRETS,DUMPIT_ALLOWED_EMAIL=$SVC-allowed-email:latest"
SECRETS="$SECRETS,DUMPIT_MAIL_FROM=$SVC-mail-from:latest"
LABEL=$(printf %s "$VERSION" | tr 'A-Z.' 'a-z-' | tr -cd 'a-z0-9_-' | cut -c1-63)

gcloud run deploy "$SVC" --image "$IMAGE" --region "$REGION" --project "$PROJECT" \
  --allow-unauthenticated --min-instances 0 --max-instances 3 \
  --set-secrets "$SECRETS" --labels "version=$LABEL" --quiet

URL=$(gcloud run services describe "$SVC" --region "$REGION" --project "$PROJECT" \
  --format 'value(status.url)')
for _ in 1 2 3 4 5 6; do
  curl -fsS "$URL/v1/health" >/dev/null 2>&1 && break
  sleep 5
done
curl -fsS "$URL/v1/health" >/dev/null || { echo "deployed, but $URL/v1/health does not answer" >&2; exit 1; }

echo "Deployed $VERSION to $ENV: $URL"
echo "Record it:  pk ship record $ENV --url $URL"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  echo "Deployed **$VERSION** to **$ENV**: $URL" >> "$GITHUB_STEP_SUMMARY"
fi
