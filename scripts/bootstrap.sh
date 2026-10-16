#!/usr/bin/env bash
# One-time: create the private, versioned bucket that holds Terraform state,
# then initialise Terraform against it.
set -euo pipefail
source "$(dirname "$0")/env.sh"

# APIs Terraform itself needs before it can manage the rest.
gcloud services enable storage.googleapis.com cloudresourcemanager.googleapis.com serviceusage.googleapis.com --project "$PROJECT_ID"

if ! gcloud storage buckets describe "gs://$TF_STATE_BUCKET" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$TF_STATE_BUCKET" \
    --project "$PROJECT_ID" --location "$REGION" \
    --uniform-bucket-level-access --public-access-prevention
  gcloud storage buckets update "gs://$TF_STATE_BUCKET" --versioning
fi

terraform -chdir="$KAWAL_ROOT/infra" init -reconfigure -backend-config="bucket=$TF_STATE_BUCKET"
echo "Bootstrap complete. Next: scripts/deploy.sh"
