# Kawal - Architecture

This document explains how Kawal is put together and why. For the one-page overview see the
[README](../README.md).

- [1. Design goals](#1-design-goals)
- [2. System context](#2-system-context)
- [3. Scam Check: the agent pipeline](#3-scam-check-the-agent-pipeline)
- [4. Live Call Guardian: fast path + deep path](#4-live-call-guardian-fast-path--deep-path)
- [5. Community intelligence: fingerprints, vectors, campaigns](#5-community-intelligence-fingerprints-vectors-campaigns)
- [6. Intel Console agents](#6-intel-console-agents)
- [7. Data model](#7-data-model)
- [8. Deployment topology (Terraform)](#8-deployment-topology-terraform)
- [9. Security model](#9-security-model)
- [10. Model choices](#10-model-choices)
- [11. Scaling beyond the prototype](#11-scaling-beyond-the-prototype)

---

## 1. Design goals

| Goal | Consequence in the design |
|---|---|
| **Intervene while the victim is being persuaded** | A streaming, sub-second detection path (Gemini Live + function calling) - not a batch classifier. |
| **Explain, don't just score** | Every verdict carries quoted evidence, a tactic taxonomy, a kill-chain stage and grounded sources. |
| **Speak the user's language** | Detection is language-agnostic; output follows the user's language (EN / BM / 中文 UI, more via Gemini). |
| **Every check protects the next person** | Redacted reports are embedded and clustered into campaigns; indicators are counted via fingerprints. |
| **Privacy by default** | No raw content is stored; indicators are HMAC'd; TTLs; browsers are read-only. |
| **Deployable by anyone** | 100% Terraform; one script deploys API + infra + web. |

## 2. System context

```mermaid
flowchart TB
  citizen(["👵 Citizen<br/>(possible victim)"])
  analyst(["🏦 Bank fraud analyst<br/>/ regulator"])

  subgraph kawal["Kawal on Google Cloud"]
    web["Web app<br/>Firebase Hosting"]
    api["kawal-api<br/>Cloud Run"]
    db[("Firestore")]
  end

  gemini["Gemini models<br/>(Vertex AI)"]
  search["Google Search"]
  webrisk["Web Risk"]
  hotline["National scam hotlines<br/>NSRC 997 · ScamShield 1799 · CICC 1326 …"]

  citizen -->|"messages, screenshots,<br/>voice notes, live calls"| web
  analyst -->|"console, bulletins,<br/>questions"| web
  web <--> api
  api <--> gemini
  gemini --> search
  api --> webrisk
  api <--> db
  web -. "real-time listeners" .-> db
  web -->|"one-tap call"| hotline
```

## 3. Scam Check: the agent pipeline

`POST /api/check` accepts text plus up to three files (images, PDFs, audio) and streams **Server-Sent Events**
so the UI shows each agent finishing. The **Evidence** agent starts *in parallel with* **Triage** whenever text
is present, so grounding costs no extra wall-clock time.

```mermaid
flowchart LR
  IN["Input<br/>text · image · PDF · audio"] --> T
  IN -. "text present" .-> E

  subgraph Agents
    T["🧠 Triage agent<br/>Gemini 3.8 Flash<br/>multimodal + JSON schema"]
    E["🌐 Evidence agent<br/>Flash-Lite + Google Search grounding<br/>+ Web Risk lookups"]
    I["🕸️ Intel agent<br/>HMAC fingerprints · embeddings<br/>Firestore KNN · campaign assignment"]
    A["📞 Advice<br/>deterministic hotline table<br/>+ tailored steps"]
  end

  T -->|"verdict, tactics, indicators,<br/>kill-chain, summary_en"| I
  T -. "media-only input" .-> E
  T --> A
  E --> OUT
  I --> OUT
  A --> OUT
  OUT["Result card<br/>+ optional redacted share"] --> DB[("Firestore")]
```

**Triage output (excerpt of the JSON schema):** `verdict` · `risk_score` · `scam_type` (14 types) ·
`red_flags[] {tactic, evidence quote, why}` (12 tactics) · `kill_chain_stage` (contact → hook → pressure →
extraction → cash-out) · `indicators[]` · `do_now[]` · `dont[]` · `pattern_name` · `summary_en` (redacted).

**Guard-rails**

- The prompt treats submitted content as *untrusted* - instructions inside a message are themselves a red flag.
- Enum outputs are clamped server-side to the taxonomy; hotline numbers come from a static, verified table,
  never from the model.
- Web Risk is authoritative: a flagged URL forces `verdict = scam`.
- A 429/503 from the primary model triggers SDK retries with back-off, then an automatic fallback model.

## 4. Live Call Guardian: fast path + deep path

The browser captures audio with an `AudioWorklet` (16 kHz, 16-bit PCM, 100 ms frames) - from the microphone, or
from a sample call that is played *and* streamed at real-time pace. Cloud Run bridges the WebSocket to a
Gemini Live session and runs a second, slower scorer on the transcript.

```mermaid
flowchart LR
  A["🎙️ Call audio<br/>PCM 16 kHz"] --> L
  subgraph fast["Fast path (sub-second)"]
    L["Gemini 3.8 Live<br/>native audio"]
    L -->|"input transcription"| TR["Transcript"]
    L -->|"tool call: flag_scam_signal<br/>(tactic, quote, risk)"| SIG["Signals"]
    L -->|"spoken warning<br/>(gated: risk ≥ 60)"| VOICE["🔊 Warning audio"]
  end
  subgraph deep["Deep path (every 2.5 s)"]
    TR --> S["Gemini 3.5 Flash-Lite<br/>structured re-score"]
    S --> R["risk · scam type · stage<br/>caller claims · advice"]
  end
  SIG --> M{{"risk = max(live, deep)"}}
  R --> M
  M -->|"≥ 70"| ALERT["🚨 Full-screen alert<br/>+ hotline button"]
```

**Why two paths?** The Live model hears tone, urgency and code-switching directly and reacts within a turn, but a
single model call is noisy as a *score*. Flash-Lite re-reads the whole transcript every 2.5 s and produces a
calibrated, explainable risk, scam type and kill-chain stage. The meter shows the max of the two; the deep path
only adds tactic chips once the call is genuinely suspicious (risk ≥ 50), which keeps legitimate calls clean.

**Live session settings**

| Setting | Value | Why |
|---|---|---|
| `response_modalities` | `AUDIO` | Native-audio model; we also enable output transcription. |
| `proactivity.proactive_audio` | `true` | Lets the model stay silent - essential for a listener. |
| `activity_handling` | `NO_INTERRUPTION` | Scammers talk over warnings; Kawal must finish its sentence. |
| VAD | high start/end sensitivity, 450 ms silence | Turn boundaries match natural call pauses. |
| Voice gate | risk ≥ 60 | Server drops any model audio before the call is clearly risky. |
| Control-token filter | strips `<no speech>`, `{pause}` | Native-audio artefacts never reach the UI. |

At the end of a call, Flash-Lite writes a summary; only the **redacted** outcome (verdict, type, tactics,
peak risk, duration) is stored - never audio or the transcript.

## 5. Community intelligence: fingerprints, vectors, campaigns

```mermaid
flowchart TB
  R["Triage result"] --> X["Extract indicators<br/>regex + model-read values"]
  X --> N["Normalise<br/>(E.164 phones, domains, accounts)"]
  N --> H["HMAC-SHA256(pepper, kind:value)<br/>pepper in Secret Manager"]
  H --> IDX[("indicators/{fp}<br/>count · countries · masked label")]

  R --> EMB["gemini-embedding-2<br/>768-d of type + pattern + summary"]
  EMB --> KNN["Firestore find_nearest<br/>COSINE, k=5"]
  KNN --> D{"distance ≤ 0.20 same type<br/>or ≤ 0.12 any type?"}
  D -->|yes| JOIN["Join campaign"]
  D -->|no| NEW["New campaign<br/>title = pattern_name"]
  JOIN --> C[("campaigns/{id}")]
  NEW --> C
```

All side-effects of a report (report doc, indicator counters, campaign counters, global stats, feed item) are
written in **one Firestore batch** so the console never shows half-written state.

## 6. Intel Console agents

- **Real-time:** the console subscribes to `feed` and `stats/global` with Firestore `onSnapshot`, so a check
  made anywhere appears within a second.
- **Bulletin agent** (`POST /api/intel/bulletin`): aggregates the last 14 days (campaign week-over-week counts,
  countries, channels, tactics) and asks Gemini 3.8 Flash (thinking: medium) for a schema-bound bulletin: threat
  level, campaign narratives, **bank controls**, **mule-account signals** and SMS advisories in EN/BM/中文.
- **Analyst agent** (`POST /api/intel/ask`): Gemini 3.8 Flash with five tools - `get_overview`,
  `list_campaigns`, `search_reports` (semantic), `daily_counts`, `lookup_indicator` (fingerprinted). Up to five
  tool rounds; the full tool trace is returned and shown so answers are auditable.

## 7. Data model

```mermaid
erDiagram
  REPORT }o--|| CAMPAIGN : "belongs to"
  REPORT }o--o{ INDICATOR : "mentions (by fingerprint)"
  REPORT ||--|| FEED_ITEM : "publishes"
  LIVE_SESSION ||--o| REPORT : "may create"

  REPORT {
    timestamp createdAt
    timestamp expireAt "TTL 180d"
    string verdict
    int riskScore
    string scamType
    string channel
    string country
    string summary "redacted EN"
    string[] tactics
    string killChainStage
    vector embedding "768-d"
    string[] indicatorFps "HMAC"
    string campaignId
    bool synthetic
  }
  INDICATOR {
    string fp PK "HMAC-SHA256"
    string kind "phone|account|domain|email|wallet"
    string masked "+6011******89"
    int count
    map countries
    map scamTypes
  }
  CAMPAIGN {
    string id PK
    string title
    string scamType
    int count
    map countries
    map channels
    string[] tactics
    timestamp firstSeen
    timestamp lastSeen
  }
  FEED_ITEM {
    timestamp createdAt
    timestamp expireAt "TTL 30d"
    string headline
    string country
    int riskScore
  }
  LIVE_SESSION {
    timestamp startedAt
    int durationS
    int maxRisk
    string verdict
    string[] tactics
    string summary "redacted"
  }
```

`stats/global` holds running counters (reports, verdicts, by type / country / channel, live sessions,
estimated loss averted) and `bulletins/*` the generated bulletins.

## 8. Deployment topology (Terraform)

```mermaid
flowchart TB
  subgraph gcp["Google Cloud project"]
    subgraph sg["asia-southeast1 (Singapore)"]
      RUN["Cloud Run: kawal-api<br/>min 1 / max 4 · 1 vCPU · 1 GiB<br/>timeout 3600 s · session affinity"]
      AR["Artifact Registry: kawal"]
      FS[("Firestore (default)<br/>vector index · TTL · rules")]
      SM["Secret Manager<br/>kawal-indicator-pepper"]
    end
    subgraph glob["Global"]
      HOST["Firebase Hosting: kawal-ai.web.app<br/>CSP · HSTS"]
      AUTH["Identity Platform<br/>anonymous sign-in"]
      KEY["API key (browser)<br/>referrer + API restricted"]
      VX["Vertex AI: Gemini (global)"]
      MON["Uptime check · budget alert"]
    end
    VXL["Vertex AI: Gemini Live (us-central1)"]
    CB["Cloud Build"]
    SA["SA kawal-api<br/>aiplatform.user · datastore.user<br/>logging · monitoring · trace"]
  end
  TF["Terraform state<br/>GCS bucket (versioned, private)"]

  CB --> AR --> RUN
  RUN -. "runs as" .-> SA
  RUN --> FS & VX & VXL
  SM -. "env secret" .-> RUN
  HOST --> RUN
  TF -.-> gcp
```

`scripts/deploy.sh` builds the image on Cloud Build, applies Terraform with the new image tag, generates the web
env from Terraform outputs and deploys Hosting. Details: [DEPLOYMENT.md](DEPLOYMENT.md).

## 9. Security model

| Threat | Mitigation |
|---|---|
| Anyone calling the API / burning Gemini quota | Firebase ID token required on every call and WebSocket; per-uid rate limits; Cloud Run max instances; budget alert. |
| Cross-site WebSocket hijacking | `Origin` must match the hosting domains; token sent in the first frame (never in the URL). |
| Leaking victims' data | Raw content never stored; HMAC fingerprints; redacted summaries; TTL; Firestore rules deny all client writes and all reads of reports/indicators/sessions. |
| Leaked credentials in a public repo | No service-account keys or API keys in code; Cloud Run uses its identity; browser key is restricted; `.gitignore` covers env/tfvars/state/keys. |
| Prompt injection inside a scam message | Content is wrapped and declared untrusted; instruction-like text is a red flag; outputs are schema-bound and clamped. |
| Malicious uploads | MIME allow-list, 8 MB cap, at most 3 files; content goes only to Gemini, never to disk. |
| XSS / clickjacking | React escaping, strict CSP (`script-src 'self'`), `frame-ancestors 'none'`, `nosniff`, HSTS. |
| Model hallucinating a hotline | Hotlines come from a static, reviewed table keyed by country. |

## 10. Model choices

| Task | Model | Reason |
|---|---|---|
| Triage (multimodal, structured) | `gemini-3.8-flash` (thinking: low) | Best reasoning on mixed-language, image and audio inputs; JSON schema. |
| Grounded evidence | `gemini-3.5-flash-lite` + Google Search | ~3 s, so it finishes inside the triage window. |
| Live listening | `gemini-3.8-live` | Native audio, function calling, proactive audio, multilingual switching. |
| Live re-scoring / call summary | `gemini-3.5-flash-lite` (thinking: minimal/low) | Runs every 2.5 s - needs to be fast and cheap. |
| Embeddings | `gemini-embedding-2` @ 768-d | Multilingual; fits Firestore's vector limits. |
| Read-aloud, sample calls | `gemini-3.8-flash-tts` | Natural BM / EN / 中文 voices. |
| Fallback on 429/503 | `gemini-3.5-flash` | Keeps the demo responsive under shared-capacity spikes. |

## 11. Scaling beyond the prototype

- **Throughput:** Cloud Run scales horizontally; Gemini calls are stateless. Move rate limiting to Firestore /
  Memorystore when running more than a handful of instances; add Provisioned Throughput for predictable latency.
- **Intel store:** Firestore handles the write pattern (one batch per report). For analytics at bank scale, stream
  reports to BigQuery and keep Firestore for the live console.
- **Integrations:** expose a signed webhook so a bank can receive "customer is on a live scam call" events and
  trigger step-up authentication or a cooling-off period on outgoing transfers.
- **On-device:** a Gemma model on Android for a private first-pass, escalating to Gemini only when risky.
