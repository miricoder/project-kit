#!/bin/sh
# Email me when Dumpit stops answering. Run once per environment, after its first deploy,
# in Google Cloud Shell:
#
#   sh scripts/setup-uptime.sh production you@example.com
#
# Google checks /v1/health every 15 minutes from several places in the world (free) and
# emails you when the checks fail for 10 minutes, and again when it is back.
set -eu

ENV=${1:-}; EMAIL=${2:-}
case "$ENV" in
  staging)    SVC=dumpit-staging ;;
  production) SVC=dumpit ;;
  *) echo "usage: sh scripts/setup-uptime.sh staging|production <email>" >&2; exit 2 ;;
esac
[ -n "$EMAIL" ] || { echo "usage: sh scripts/setup-uptime.sh $ENV <email>" >&2; exit 2; }
PROJECT=${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}
REGION=${GCP_REGION:-europe-west1}
URL=$(gcloud run services describe "$SVC" --region "$REGION" --project "$PROJECT" --format 'value(status.url)')
[ -n "$URL" ] || { echo "$SVC is not deployed yet; deploy first" >&2; exit 1; }
HOST=${URL#https://}

CHANNEL=$(gcloud beta monitoring channels list --project "$PROJECT" \
  --filter "labels.email_address=\"$EMAIL\"" --format 'value(name)' | head -1)
[ -n "$CHANNEL" ] || CHANNEL=$(gcloud beta monitoring channels create --project "$PROJECT" \
  --display-name "Dumpit alerts ($EMAIL)" --type email \
  --channel-labels "email_address=$EMAIL" --format 'value(name)')

CHECK=$(gcloud monitoring uptime list-configs --project "$PROJECT" \
  --filter "displayName=\"$SVC health\"" --format 'value(name)' | head -1)
[ -n "$CHECK" ] || CHECK=$(gcloud monitoring uptime create "$SVC health" --project "$PROJECT" \
  --resource-type uptime-url --resource-labels "host=$HOST,project_id=$PROJECT" \
  --protocol https --path /v1/health --period 15 --timeout 10 --format 'value(name)')
CHECK_ID=${CHECK##*/}

POLICY=$(mktemp)
cat > "$POLICY" <<JSON
{
  "displayName": "$SVC is down",
  "combiner": "OR",
  "conditions": [{
    "displayName": "$SVC /v1/health is failing",
    "conditionThreshold": {
      "filter": "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.label.check_id=\"$CHECK_ID\" AND resource.type=\"uptime_url\"",
      "aggregations": [{"alignmentPeriod": "1200s", "perSeriesAligner": "ALIGN_NEXT_OLDER",
                        "crossSeriesReducer": "REDUCE_COUNT_FALSE", "groupByFields": ["resource.label.*"]}],
      "comparison": "COMPARISON_GT", "thresholdValue": 1, "duration": "600s",
      "trigger": {"count": 1}
    }
  }],
  "notificationChannels": ["$CHANNEL"]
}
JSON
if gcloud alpha monitoring policies list --project "$PROJECT" --format 'value(displayName)' | grep -qx "$SVC is down"; then
  echo "Alert already set for $SVC"
else
  gcloud alpha monitoring policies create --project "$PROJECT" --policy-from-file "$POLICY" >/dev/null
  echo "Alert set: $EMAIL hears about it when $URL stops answering"
fi
rm -f "$POLICY"
