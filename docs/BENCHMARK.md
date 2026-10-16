# Benchmarks

All numbers were measured on **16 Oct 2026** against the deployed stack (Cloud Run in `asia-southeast1`,
Gemini on Vertex AI) unless stated otherwise. Raw output is committed next to this file:
[`benchmark-triage.json`](benchmark-triage.json) and [`benchmark-live.log`](benchmark-live.log).

> **Honest caveat:** the evaluation sets are small and labelled by the team. They show the system works
> end-to-end and is well-calibrated on realistic cases; they are not a substitute for a large, independently
> labelled evaluation, which is on the roadmap.

## 1. Scam Check - classification quality

**Set:** 30 held-out messages (not used for prompting or seeding) - 20 scams that the model assigned to 9 distinct scam types and
10 *deliberately tricky* legitimate messages (real-format bank OTP and debit alerts that mention codes and
hotlines, courier delivery notices, an app verification code, a family text, a clinic reminder, a work e-mail).
Languages: English, Bahasa Melayu, 中文, Bahasa Indonesia. Countries: MY, SG, ID, PH, TH, AU, IN, HK.

**Rule:** Kawal "warns" if the verdict is `scam` or `suspicious`.

**Reproduce:** `PROJECT_ID=<project> python scripts/evaluate.py --out docs/benchmark-triage.json`

| Metric | `gemini-3.8-flash` (thinking: low) |
|---|---|
| Accuracy | **1.00** (30 / 30) |
| Precision | **1.00** |
| Recall | **1.00** |
| False-positive rate | **0.00** (0 / 10 legitimate messages flagged) |
| Mean risk score - scams | 98.4 |
| Mean risk score - legitimate | 5.0 |
| Triage latency p50 / p95 / max | **5.3 s / 6.7 s / 8.2 s** |

Confusion matrix: TP 20 · TN 10 · FP 0 · FN 0.

## 2. Scam Check - end-to-end latency in production

Measured with `curl` against `https://kawal-api-…run.app/api/check` (SSE), Firebase ID token attached:

| Input | Verdict | Total | Triage | Evidence (parallel) | Intel |
|---|---|---|---|---|---|
| BM LHDN refund phishing SMS | scam · 98 | **5.0 s** | 4.6 s | 2.2 s | 0.5 s |
| EN legitimate card alert | likely safe · 5 | **4.1 s** | 3.7 s | 2.3 s | 0.4 s |
| EN “Hi Mum” new-number scam | scam · 95 | **6.9 s** | 6.5 s | 1.8 s | 0.4 s |

Design choices that bought the latency: the Evidence agent (Flash-Lite + Google Search grounding, ≈ 2-3 s) starts
**in parallel** with triage; community intel (embedding + Firestore KNN + fingerprint lookup) adds ≈ 0.4 s; results
stream stage-by-stage so the user sees progress within ~100 ms.

Component timings (local profile): embedding 0.4 s · Firestore KNN (k = 5) 0.3 s · fingerprint lookup 0.05 s.

## 3. Live Call Guardian - real-time detection

**Method:** `scripts/live_client.py` streams each synthetic call (Gemini TTS, 24 kHz → 16 kHz PCM) to the production
WebSocket **at real-time pace** (100 ms chunks), exactly as the browser does. Times are seconds from session start;
the first spoken line ends at ≈ 11 s because each sample opens with a long first sentence.

| Sample call | First tactic flagged | First alert | Tactics caught (in order) | Peak risk | Spoken warning | Verdict |
|---|---|---|---|---|---|---|
| 🇲🇾 Macau scam - fake PDRM + “safe account” (BM, 50 s) | 11.3 s (+0.2 s after sentence) | 22.3 s - right after the money-laundering accusation | authority → fear/threat → secrecy → **safe account** → urgency | **98** | “Ini satu penipuan, sila letak telefon sekarang…” | scam |
| 🇸🇬 Fake bank fraud team - OTP + remote app (EN, 41 s) | 12.0 s | **25.1 s - 0.1 s after “read me the 6-digit code”** | authority → **credential request** → fear → **remote access** → urgency | **98** | “This is a scam…” | scam |
| 🇨🇳 Parcel held by customs + fake police (中文, 41 s) | 11.6 s | **11.6 s** | authority → fear → secrecy → **safe account** → urgency | **98** | “这是诈骗，请立刻挂断…” | scam |
| ✅ Genuine card-services call (EN, 35 s, control) | - | **none** | none | low | **none** | likely safe |

Observations:

- **Reaction time** to a new tactic is ≈ 0.1-0.5 s after the speaker finishes the sentence (Live tool call),
  i.e. the alert lands *before the victim can answer*.
- The **dual path** works as intended: Live flags tactics instantly; Flash-Lite adds tactics Live missed (e.g.
  urgency) and keeps the meter calibrated. On the control call the deep path held risk ≤ 5 after the caller said
  they would never ask for a PIN or code.
- After switching the Live session to `activity_handling = NO_INTERRUPTION`, spoken warnings complete even while
  the scammer keeps talking (e.g. *“Ini adalah corak penipuan, tolong letakkan talian dan hubungi NSRC di 997.”*).
- End-of-call summary arrives ≈ 4 s after the user ends the call.

## 4. Infrastructure

| Check | Result |
|---|---|
| Cold start | avoided - `min_instances = 1` |
| Unauthenticated `POST /api/check` | `401` |
| CORS pre-flight from a foreign origin | rejected (`400`) |
| Security headers (API) | `nosniff`, `X-Frame-Options: DENY`, `no-referrer` |
| Security headers (web) | CSP (`script-src 'self'`), HSTS, Permissions-Policy (mic only) |
| Terraform plan after deploy | **No changes** (no drift) |
| Unit tests / lint | 13 passed · ruff clean |

## 5. How to re-run everything

```bash
# accuracy
PROJECT_ID=$PROJECT_ID python scripts/evaluate.py --out docs/benchmark-triage.json

# live guardian against production (needs a Firebase ID token for the web app)
python scripts/live_client.py frontend/public/samples/macau-scam-ms.m4a --lang ms \
  --url wss://<api-host>/ws/live --token <ID_TOKEN>

# unit tests
cd backend && pytest && ruff check app tests
```
