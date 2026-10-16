#!/usr/bin/env bash
# Build and deploy everything:
#   1. API container  -> Cloud Build -> Artifact Registry
#   2. Infrastructure -> Terraform (Cloud Run, Firestore, Firebase, IAM, ...)
#   3. Web app        -> Vite build -> Firebase Hosting
#
# Usage: scripts/deploy.sh [all|api|web]
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$KAWAL_ROOT"

WHAT="${1:-all}"
TF="terraform -chdir=infra"
REPO="$REGION-docker.pkg.dev/$PROJECT_ID/kawal"
TAG="$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)"
[ -n "$(git status --porcelain 2>/dev/null)" ] && TAG="$TAG-$(date +%H%M%S)"

if [[ "$WHAT" == "all" || "$WHAT" == "api" ]]; then
  IMAGE="$REPO/api:$TAG"
  echo "==> Building $IMAGE with Cloud Build"
  gcloud builds submit backend --project "$PROJECT_ID" --tag "$IMAGE" --quiet

  echo "==> Applying Terraform"
  $TF apply -auto-approve -var "project_id=$PROJECT_ID" -var "api_image=$IMAGE"
fi

if [[ "$WHAT" == "all" || "$WHAT" == "web" ]]; then
  echo "==> Writing frontend/.env.production from Terraform outputs"
  python3 scripts/write_web_env.py

  echo "==> Building web app"
  (cd frontend && npm ci --no-fund --no-audit && npm run build)

  echo "==> Deploying to Firebase Hosting"
  npx --yes firebase-tools@15.34.0 deploy --only hosting --project "$PROJECT_ID" --non-interactive
fi

echo "Done: $($TF output -raw hosting_url)"
