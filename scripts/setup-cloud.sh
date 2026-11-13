#!/bin/sh
# One-time Google Cloud setup for Dumpit. Run it in Google Cloud Shell
# (console.cloud.google.com, the >_ button at the top right), in a clone of the repository:
#
#   gcloud config set project <your-project-id>
#   sh scripts/setup-cloud.sh miricoder/project-kit       # the GitHub repository that deploys
#
# It turns on the services Dumpit uses, makes a place for its images, lets GitHub Actions
# deploy without any stored key (Workload Identity Federation, limited to that one
# repository), and sets a small budget alert. Safe to run again. At the end it prints the four
# values to add to GitHub.
set -eu

REPO=${1:-}
case "$REPO" in */*) ;; *) echo "usage: sh scripts/setup-cloud.sh <github-owner>/<repo>" >&2; exit 2 ;; esac
PROJECT=${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}
[ -n "$PROJECT" ] || { echo "set a project: gcloud config set project <id>" >&2; exit 2; }
REGION=${GCP_REGION:-europe-west1}
NUMBER=$(gcloud projects describe "$PROJECT" --format 'value(projectNumber)')
RUNTIME_SA="$NUMBER-compute@developer.gserviceaccount.com"
DEPLOY_SA="dumpit-deployer@$PROJECT.iam.gserviceaccount.com"
POOL="projects/$NUMBER/locations/global/workloadIdentityPools/github"

echo "1/5 Turning on services"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  monitoring.googleapis.com billingbudgets.googleapis.com cloudbilling.googleapis.com \
  --project "$PROJECT"

echo "2/5 Image repository"
gcloud artifacts repositories describe dumpit --location "$REGION" --project "$PROJECT" >/dev/null 2>&1 \
  || gcloud artifacts repositories create dumpit --repository-format docker \
       --location "$REGION" --project "$PROJECT" --description "Dumpit images"

echo "3/5 Permissions: the running app reads its secrets; the deployer deploys"
gcloud projects add-iam-policy-binding "$PROJECT" --condition=None --quiet \
  --member "serviceAccount:$RUNTIME_SA" --role roles/secretmanager.secretAccessor >/dev/null
gcloud iam service-accounts describe "$DEPLOY_SA" --project "$PROJECT" >/dev/null 2>&1 \
  || gcloud iam service-accounts create dumpit-deployer --project "$PROJECT" \
       --display-name "Dumpit deploys from GitHub Actions"
for ROLE in roles/run.admin roles/artifactregistry.writer; do
  gcloud projects add-iam-policy-binding "$PROJECT" --condition=None --quiet \
    --member "serviceAccount:$DEPLOY_SA" --role "$ROLE" >/dev/null
done
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" --project "$PROJECT" --quiet \
  --member "serviceAccount:$DEPLOY_SA" --role roles/iam.serviceAccountUser >/dev/null

echo "4/5 GitHub Actions may act as the deployer, from $REPO only"
gcloud iam workload-identity-pools describe github --location global --project "$PROJECT" >/dev/null 2>&1 \
  || gcloud iam workload-identity-pools create github --location global --project "$PROJECT" \
       --display-name "GitHub Actions"
gcloud iam workload-identity-pools providers describe github --workload-identity-pool github \
    --location global --project "$PROJECT" >/dev/null 2>&1 \
  || gcloud iam workload-identity-pools providers create-oidc github --project "$PROJECT" \
       --location global --workload-identity-pool github --display-name "GitHub" \
       --issuer-uri "https://token.actions.githubusercontent.com" \
       --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository" \
       --attribute-condition "assertion.repository == '$REPO'"
gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA" --project "$PROJECT" --quiet \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/$POOL/attribute.repository/$REPO" >/dev/null

echo "5/5 Budget alert (emails the billing account's admins)"
BILLING=$(gcloud billing projects describe "$PROJECT" --format 'value(billingAccountName)' | sed 's#.*/##')
if [ -z "$BILLING" ]; then
  echo "  no billing account linked: link one in Billing, then run this again"
elif gcloud billing budgets list --billing-account "$BILLING" --format 'value(displayName)' 2>/dev/null | grep -qx "Dumpit"; then
  echo "  already set"
else
  CURRENCY=$(gcloud billing accounts describe "$BILLING" --format 'value(currencyCode)' 2>/dev/null || echo EUR)
  gcloud billing budgets create --billing-account "$BILLING" --display-name Dumpit \
      --budget-amount "${BUDGET:-5}${CURRENCY}" --filter-projects "projects/$PROJECT" \
      --threshold-rule percent=0.2 --threshold-rule percent=1.0 >/dev/null \
    && echo "  emails at 20% and 100% of ${BUDGET:-5} $CURRENCY a month" \
    || echo "  could not create it here; add one in Billing > Budgets & alerts"
fi

cat <<DONE

Done. Add these four in GitHub: $REPO > Settings > Secrets and variables > Actions >
Variables tab > New repository variable (they are not secret):

  GCP_PROJECT       $PROJECT
  GCP_REGION        $REGION
  GCP_WIF_PROVIDER  $POOL/providers/github
  GCP_DEPLOY_SA     $DEPLOY_SA

Next: sh scripts/setup-secrets.sh staging
DONE
