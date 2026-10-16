# Deployment guide

Everything Kawal needs on Google Cloud is declared in [`infra/`](../infra) (Terraform) and deployed with two
scripts. A fresh project goes from zero to a live URL in roughly 15 minutes (most of it is Firestore building
its vector index).

## What gets created

| Resource | Purpose |
|---|---|
| 19 Google APIs | Vertex AI, Cloud Run, Firestore, Firebase, Identity Toolkit, Web Risk, Secret Manager, … |
| Service account `kawal-api` | Runtime identity for Cloud Run (Vertex AI user, Datastore user, logging, metrics, tracing) |
| Artifact Registry `kawal` | API container images (keeps the 10 most recent) |
| Secret `kawal-indicator-pepper` | Random 48-char pepper for HMAC indicator fingerprints |
| Firestore `(default)` in `asia-southeast1` | Data store, KNN vector index (768-d), composite index, TTL policies, security rules |
| Firebase project, web app, Hosting site | Web app hosting; `kawal-ai.web.app` by default |
| Identity Platform config | Anonymous sign-in, authorised domains |
| Restricted browser API key | Only our origins; only Identity Toolkit, Secure Token, Firestore, Installations |
| Cloud Run service `kawal-api` | API + WebSockets; scale to zero, max 2 instances, 512 MiB |
| App Check | reCAPTCHA Enterprise key, App Check registration, enforcement on Firestore + Auth |
| Budget + circuit breaker | Budget (MYR 20 default) → Pub/Sub → `/internal/budget` kill switch |
| Monitoring | uptime check every 15 min; alerts for budget breaker, abuse spikes, downtime |

## Prerequisites

- A Google Cloud project **with billing enabled**, and Owner (or equivalent) on it.
- `gcloud`, Terraform ≥ 1.9, Python 3.13, Node.js 20+.
- Application Default Credentials for Terraform and the Firebase CLI:
  `gcloud auth application-default login` - or, to keep a separate account, set `KAWAL_ADC_FILE` to a
  credentials file and `KAWAL_GCLOUD_CONFIG` to a dedicated gcloud configuration (see `scripts/env.sh`).

## 1. Configure

```bash
export PROJECT_ID=your-project-id
cp infra/terraform.tfvars.example infra/terraform.tfvars
# edit: project_id, billing_account (enables budget + circuit breaker), alert_email,
#       optionally hosting_site_id and appcheck_debug_token (a UUID, for headless tests only)
```

`hosting_site_id` becomes `<id>.web.app` and must be globally unique.

## 2. Bootstrap (once)

```bash
./scripts/bootstrap.sh
```

Enables the APIs Terraform needs to start, creates a private versioned bucket `<project>-tfstate` for state,
and runs `terraform init`.

## 3. Deploy

```bash
./scripts/deploy.sh          # API + infrastructure + web
./scripts/deploy.sh api      # rebuild the API image and roll Cloud Run
./scripts/deploy.sh web      # rebuild and redeploy the web app only
```

`deploy.sh` will:

1. build `backend/` on **Cloud Build** and push `…/kawal/api:<git-sha>` to Artifact Registry,
2. `terraform apply` with that image,
3. write `frontend/.env.production` from Terraform outputs (`scripts/write_web_env.py`),
4. `npm ci && npm run build`, then `firebase deploy --only hosting`.

## 4. Seed demo data (optional)

The Intel Console is more meaningful with history. Seed ~45 clearly-labelled **synthetic** reports, using the
production pepper so fingerprints match live traffic:

```bash
INDICATOR_PEPPER=$(gcloud secrets versions access latest --secret kawal-indicator-pepper) \
PROJECT_ID=$PROJECT_ID python scripts/seed_intel.py
```

## 5. Verify

```bash
curl https://<api-url>/api/health                       # {"status":"ok"}
curl -X POST https://<api-url>/api/check -F text=hi     # 401 - a Firebase ID token is required
python scripts/live_client.py frontend/public/samples/macau-scam-ms.m4a --lang ms \
  --url wss://<api-url>/ws/live --token <Firebase ID token>
```

## Local development

```bash
# API
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env            # AUTH_REQUIRED=false is for local development only
.venv/bin/uvicorn app.main:app --reload --port 8080
.venv/bin/pytest && .venv/bin/ruff check app tests

# Web
cd frontend
npm install
cp .env.example .env.local      # VITE_API_BASE=http://localhost:8080 + your Firebase web config
npm run dev                     # http://localhost:5173
```

## Regenerating the sample calls

```bash
python scripts/generate_sample_calls.py --project $PROJECT_ID   # Gemini TTS, needs ffmpeg
```

## Costs

Typical bill ≈ MYR 0-5 / month (Cloud Run scales to zero; everything else sits in free tiers; Gemini at demo
traffic). Ceilings, alerts and the budget circuit breaker are described in [COST_CONTROLS.md](COST_CONTROLS.md).

## Tear down

```bash
terraform -chdir=infra destroy
```

Firestore is configured with `deletion_policy = ABANDON` and delete protection, so data survives an accidental
destroy; delete the database manually if you really want it gone.
