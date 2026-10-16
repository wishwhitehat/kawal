# Handover & knowledge-transfer guide

For the engineer taking over Kawal. Read this top to bottom once, then run the **60-minute KT session** in
§ 9 with the outgoing owner. Nothing secret is in this file - credentials are handed over separately (see § 2).

- [1. Kawal in five minutes](#1-kawal-in-five-minutes)
- [2. Access checklist](#2-access-checklist)
- [3. Get it running locally](#3-get-it-running-locally)
- [4. Code tour](#4-code-tour)
- [5. How a request flows](#5-how-a-request-flows)
- [6. Deploying](#6-deploying)
- [7. Runbooks](#7-runbooks)
- [8. Known limitations & tech debt](#8-known-limitations--tech-debt)
- [9. KT session script (60 min)](#9-kt-session-script-60-min)
- [10. Glossary](#10-glossary)

---

## 1. Kawal in five minutes

| | |
|---|---|
| **What** | Real-time, multilingual scam interception: a **Live Call Guardian** (Gemini Live listens to a speakerphone call and warns the victim), a **Scam Check** (multi-agent analysis of messages / screenshots / voice notes) and an **Intel Console** for banks. |
| **Why** | Most scam losses in Asia-Pacific are transfers victims make themselves while being manipulated live; existing tools act after the fact. |
| **Stack** | React SPA on Firebase Hosting → FastAPI on Cloud Run → Gemini (Vertex AI) + Firestore. Terraform for everything. |
| **Live** | https://kawal-ai.web.app · API https://kawal-api-gb6wisvuia-as.a.run.app/api/health |
| **Docs** | [README](../README.md) · [ARCHITECTURE](ARCHITECTURE.md) · [COST_CONTROLS](COST_CONTROLS.md) · [DEPLOYMENT](DEPLOYMENT.md) · [BENCHMARK](BENCHMARK.md) · [SECURITY](../SECURITY.md) |

Mental model: **three products, one backend, one database.** Every AI call goes through `app/guard.py`
(cost & abuse controls) and every write goes through `app/store.py`.

## 2. Access checklist

Ask the outgoing owner for each of these; tick them off during the KT session.

| Access | Why you need it | How it's granted |
|---|---|---|
| GitHub `wishwhitehat/kawal` - *Write* (or *Maintain*) | push, review Dependabot PRs | Repo → Settings → Collaborators |
| GCP project `japac-ai-builder-cup-26` - *Owner* (or Editor + Project IAM Admin) | deploy, logs, Firestore | IAM → Grant access |
| Billing account - *Billing Account Viewer* (budget changes need *Costs Manager*) | watch spend, edit budget | Billing → Account management |
| Firebase console (same project) | Hosting, Auth, App Check, Firestore data | inherited from GCP IAM |
| Alert e-mail | budget / breaker / abuse / downtime alerts | add your address as `alert_email` (or a second notification channel) |
| `infra/terraform.tfvars` | billing account, alert e-mail, App Check debug token | **hand over privately** (password manager) - never commit |

Secrets that exist (and where):

| Secret | Lives in | Notes |
|---|---|---|
| HMAC pepper for indicator fingerprints | Secret Manager `kawal-indicator-pepper` | Rotating it orphans existing fingerprints (counts restart). |
| App Check debug token | `terraform.tfvars` → Firebase App Check | Only for headless tests / video recording. Rotate if shared. |
| Terraform state | GCS `japac-ai-builder-cup-26-tfstate` (private, versioned) | Contains the pepper - treat as secret. |

There are **no** API keys or service-account keys anywhere: Cloud Run uses its own identity, local dev uses your
own `gcloud` credentials.

## 3. Get it running locally

```bash
git clone https://github.com/wishwhitehat/kawal && cd kawal

# credentials for local dev (uses YOUR Google account)
gcloud auth application-default login
gcloud config set project japac-ai-builder-cup-26

# backend
cd backend
python3.13 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env          # AUTH_REQUIRED=false, APPCHECK_REQUIRED stays false locally
.venv/bin/pytest && .venv/bin/ruff check app tests
.venv/bin/uvicorn app.main:app --reload --port 8080

# frontend (new terminal)
cd frontend && npm install
cp .env.example .env.local    # VITE_API_BASE=http://localhost:8080 + Firebase web config
#   (get the web config with: python scripts/write_web_env.py .env.local, then set VITE_API_BASE back to localhost
#    and leave VITE_RECAPTCHA_SITE_KEY empty so App Check is off locally)
npm run dev                   # http://localhost:5173

# optional: protect your commits
pip install pre-commit && pre-commit install
```

Quick sanity checks: `curl localhost:8080/api/health`, then run the Live Guardian without a browser:
`backend/.venv/bin/python scripts/live_client.py frontend/public/samples/macau-scam-ms.m4a --lang ms`.

> Local dev writes to the **production** Firestore unless you point `PROJECT_ID` at a sandbox project. Use
> `share=false` (untick "Share anonymously") while testing so you don't pollute the intel data.

## 4. Code tour

```
backend/app/
  main.py          HTTP routes: /api/check (SSE), /api/tts, /api/intel/*, /api/usage, /internal/budget, /ws/live
  guard.py         ⭐ cost & abuse: kill switch, App Check, daily quotas, result cache
  auth.py          Firebase ID-token verification, per-minute RateLimiter
  pipeline.py      Scam Check orchestration (Triage → Evidence ∥ Intel → Advice → Share)
  agents/
    triage.py      Gemini 3.8 Flash multimodal + JSON schema - the "brain"; prompt lives here
    evidence.py    Flash-Lite + Google Search grounding; Web Risk lookups
    intel.py       HMAC fingerprints, embeddings, Firestore KNN, campaign assignment (thresholds here)
    bulletin.py    threat-bulletin writer
    analyst.py     "Ask Kawal Intel" tool-calling agent (tools + topic guard)
  live.py          ⭐ Live Guardian: WebSocket ⇄ Gemini Live, deep scorer, voice gate, summary
  store.py         all Firestore reads/writes (one batch per report)
  redact.py        PII redaction, indicator extraction & masking
  taxonomy.py      scam types, tactics, kill-chain, hotlines (static, reviewed)
  config.py        every tunable (models, limits, windows) - env-driven
frontend/src/
  pages/           CheckPage, LivePage, IntelPage, HowPage
  lib/             api.ts (fetch + SSE + App Check header), audio.ts (AudioWorklet, PCM player),
                   firebase.ts (Auth + App Check), i18n.ts (EN/BM/中文 strings)
infra/             Terraform: main (APIs, IAM, secrets, registry), firestore, firebase, run,
                   guardrails (App Check, budget breaker, alerts), monitoring (uptime, budget)
scripts/           bootstrap, deploy, seed_intel, evaluate, live_client, generate_sample_calls, write_web_env
```

Where to change common things:

| I want to… | Edit |
|---|---|
| Improve scam detection quality | `agents/triage.py` `SYSTEM` prompt; re-run `scripts/evaluate.py` |
| Make live alerts more/less sensitive | `live.py` `LIVE_SYSTEM`, `SCORE_SYSTEM`, `SPEAK_THRESHOLD`, `DEEP_SIGNAL_MIN_RISK`, alert threshold (70) in `maybe_alert` |
| Add a country / hotline | `taxonomy.py` `HOTLINES` + `frontend/src/components/ui.tsx` `COUNTRIES` |
| Add a UI language | `frontend/src/lib/i18n.ts` (+ `LANGS` in `taxonomy.py`) |
| Change a model | `config.py` (`model_flash`, `model_lite`, `model_live`, …) or Cloud Run env |
| Change quotas / budget | `infra/variables.tf` → `terraform.tfvars` (see COST_CONTROLS § 5) |
| Change campaign clustering | `agents/intel.py` `SAME_CAMPAIGN*` thresholds |

## 5. How a request flows

**Scam Check:** browser → `POST /api/check` with `Authorization: Bearer <Firebase ID token>` and
`X-Firebase-AppCheck` → `guard.ensure_open` → `guard.app_check_dep` → per-minute limit → cache lookup →
`guard.consume("check")` → `pipeline.check()` streams SSE `stage` events, then a `result`. Evidence starts in
parallel with triage. Optional share → `store.save_report()` writes report + indicators + campaign + stats + feed
in one batch.

**Live Guardian:** browser opens `wss://…/ws/live`, first frame `{"type":"start", token, appCheck, lang, country}`
→ checks + `consume("live")` → `LiveGuardian.run()` opens a Gemini Live session; three tasks: `pump_client`
(PCM 16 kHz in), `pump_model` (transcripts, `flag_scam_signal` tool calls, gated voice out), `score_loop`
(Flash-Lite every 3 s). On stop → summary → redacted session + optional report.

Diagrams for both: [ARCHITECTURE.md § 3-4](ARCHITECTURE.md#3-scam-check-the-agent-pipeline).

## 6. Deploying

```bash
export KAWAL_GCLOUD_CONFIG=<your gcloud configuration>   # optional; keeps this project's account separate
export KAWAL_ADC_FILE=<path to credentials json>         # optional; otherwise your global ADC is used
./scripts/deploy.sh          # everything: Cloud Build → Terraform → web build → Firebase Hosting
./scripts/deploy.sh api      # backend only
./scripts/deploy.sh web      # frontend only
```

Always: `pytest`, `ruff check`, `npx tsc --noEmit` before deploying; `terraform -chdir=infra plan` should show
only the image change. After deploying, smoke test: `/api/health`, one Scam Check in the browser, one sample
Live call. Full guide: [DEPLOYMENT.md](DEPLOYMENT.md).

## 7. Runbooks

| Situation | What to do |
|---|---|
| **Budget alert e-mail** | Check Billing → Reports for which SKU grew. Look at `/api/usage` and Cloud Run logs for `quota_exceeded`. If abuse: lower `global_daily` caps and redeploy. |
| **"Breaker engaged" alert / site says "paused"** | The monthly budget was reached. Either wait for the new month (auto-resumes) or raise `budget_amount` and set Firestore `config/runtime.paused=false`. |
| **Abuse-spike alert** | Logs: `textPayload:"quota_exceeded"`; look at the `scope` (global/user/ip). Caps already bound spend - consider tightening `ip_daily`. |
| **API down alert** | `gcloud run services describe kawal-api --region asia-southeast1`; check latest revision logs; roll back: `gcloud run services update-traffic kawal-api --to-revisions <prev>=100 --region asia-southeast1`. |
| **Users see "App Check token invalid"** | Domain not in the reCAPTCHA key's `allowed_domains` (Terraform `guardrails.tf`), or an ad-blocker blocks `google.com/recaptcha`. Temporary bypass: `appcheck_enforce=false` + deploy. |
| **Gemini 429 / slow** | Shared capacity spike. The SDK retries and falls back to `model_fallback`; if persistent, switch `model_flash` to a less busy model or request quota. |
| **Live call never alerts** | Run `scripts/live_client.py` with the sample; check logs for `deep scorer failed`; verify `MODEL_LIVE` is available in `LIVE_LOCATION`. |
| **Need to pause everything now** | Firestore → `config/runtime` → `paused: true` (effective in ≤ 30 s). |
| **Suspected leaked secret** | Rotate it (pepper: add a new Secret Manager version and redeploy; debug token: change in tfvars and apply), then run `gitleaks git .` on the repo. |
| **Reset demo data** | Delete Firestore collections `reports`, `indicators`, `campaigns`, `feed`, `stats`, `bulletins`, then `scripts/seed_intel.py` with the production pepper (see DEPLOYMENT § 4). |

Useful commands:

```bash
gcloud run services logs read kawal-api --region asia-southeast1 --limit 100
gcloud logging read 'resource.labels.service_name="kawal-api" AND severity>=WARNING' --freshness 1h --limit 50
curl -s https://kawal-api-gb6wisvuia-as.a.run.app/api/usage | jq
terraform -chdir=infra plan
```

## 8. Known limitations & tech debt

- **Evaluation is small** (30 messages, 4 calls, team-labelled). Build a larger, independently labelled set before
  claiming accuracy publicly.
- **Per-minute rate limiter is in-memory** per Cloud Run instance (daily quotas are global in Firestore). Fine at
  max 2 instances; move to Firestore / Memorystore if you scale out.
- **Live API is in `us-central1`** (Gemini 3.8 Live availability) while everything else is in Singapore - audio
  leaves the region during calls. Revisit when the model is available in Asia.
- **Campaign titles** come from the first report's `pattern_name`; they don't get renamed as the cluster grows.
- **Sample calls and seed data are synthetic** and labelled as such; `stats/global` includes them.
- **CI workflow** (`.github/workflows/ci.yml`) needs a GitHub token with the `workflow` scope to be pushed.
- **No automated end-to-end tests** for the frontend; the Live Guardian is covered by `scripts/live_client.py`.
- The analyst agent's answers are only as good as the (unverified) community data - it says so in its replies.

## 9. KT session script (60 min)

Run this as a screen-share. The outgoing owner drives for the first half, the new owner for the second.

| Time | Topic | Outgoing owner says / shows | New owner does |
|---|---|---|---|
| 0-5 | **Why Kawal exists** | The problem (self-effected transfers during calls), the three products, the judging criteria it was built for. | Asks questions. |
| 5-15 | **Live demo** | kawal-ai.web.app: sample Macau-scam call → alert; genuine bank call → silence; Scam Check with an example; Intel Console bulletin + Ask Intel. | Repeats one flow themselves. |
| 15-25 | **Architecture** | Walk the README diagram, then ARCHITECTURE § 3-5. Emphasise: dual path in `live.py`, parallel agents in `pipeline.py`, one-batch writes in `store.py`. | Opens each file as it's mentioned. |
| 25-32 | **Cost & abuse controls** | COST_CONTROLS diagram; show `/api/usage`, Firestore `config/runtime`, the budget, alert policies in Cloud Monitoring. | Toggles `paused` true → sees 503 → false. |
| 32-40 | **Access handover** | Grant GitHub + GCP + billing access; share `terraform.tfvars` via password manager. | Ticks § 2 checklist; adds own alert e-mail. |
| 40-50 | **Hands-on** | Observes. | Runs backend tests locally; runs `scripts/live_client.py`; changes a harmless string, deploys with `scripts/deploy.sh web`, verifies. |
| 50-55 | **Runbooks & on-call** | Walk § 7: breaker, abuse, rollback, App Check issues. | Asks "what if" questions. |
| 55-60 | **What's next** | § 8 tech debt and the roadmap in the README; agree first tasks. | Writes down owners and dates. |

After the session, the new owner should be able to answer:

1. Where would you change how sensitive the live alert is?
2. How do you pause all AI spend in under a minute?
3. What happens when the monthly budget is reached, and how does it resume?
4. Why does a repeated identical check cost nothing?
5. Which secret, if rotated, resets indicator counts - and why?

## 10. Glossary

| Term | Meaning |
|---|---|
| **Kill chain** | contact → hook → pressure → extraction → cash-out; where the victim is in the scam |
| **Tactic** | one of 12 manipulation techniques (authority impersonation, safe account, secrecy, …) |
| **Fast / deep path** | Gemini Live tool calls (sub-second) vs Flash-Lite transcript re-scoring (every 3 s) |
| **Indicator / fingerprint** | phone, account, domain, wallet; stored only as an HMAC with a masked label |
| **Campaign** | cluster of similar reports (Gemini embeddings + Firestore KNN) |
| **Kill switch / breaker** | `config/runtime.paused`, set by hand or by the budget → Pub/Sub → `/internal/budget` path |
| **App Check** | Firebase attestation (reCAPTCHA Enterprise) proving requests come from the real web app |
| **NSRC 997** | Malaysia's National Scam Response Centre hotline |
