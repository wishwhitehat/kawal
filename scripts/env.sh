# shellcheck shell=bash
# Shared settings for the helper scripts. Source it:  source scripts/env.sh
#
# Override any of these in your shell before sourcing. KAWAL_GCLOUD_CONFIG lets
# you keep this project on a dedicated gcloud configuration (gcloud config
# configurations create kawal), separate from your day-to-day account.

export PROJECT_ID="${PROJECT_ID:-japac-ai-builder-cup-26}"
export REGION="${REGION:-asia-southeast1}"
export TF_STATE_BUCKET="${TF_STATE_BUCKET:-${PROJECT_ID}-tfstate}"

if [ -n "${KAWAL_GCLOUD_CONFIG:-}" ]; then
  export CLOUDSDK_ACTIVE_CONFIG_NAME="$KAWAL_GCLOUD_CONFIG"
fi

# Terraform / firebase-tools / Python SDKs use Application Default Credentials.
# If you don't want to touch your global ADC, point at a per-account file instead.
if [ -n "${KAWAL_ADC_FILE:-}" ]; then
  export GOOGLE_APPLICATION_CREDENTIALS="$KAWAL_ADC_FILE"
fi
export GOOGLE_CLOUD_QUOTA_PROJECT="$PROJECT_ID"

KAWAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
export KAWAL_ROOT
