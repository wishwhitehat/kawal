# Submission form text

Copy-paste material for the Hack2skill submission form.

## Project name
Kawal - real-time, multilingual scam interception for Asia-Pacific

## Theme / problem statement
BFSI: Intelligent Risk, Fraud & Financial Experiences

## Links
- **Deployed prototype:** https://kawal-ai.web.app
- **GitHub repository:** https://github.com/wishwhitehat/kawal
- **Demo video:** https://drive.google.com/file/d/1wYByug6AXhn4cdVww69Z02nbbA-v2ERV/view?usp=drive_link
- **API health (for judges):** https://kawal-api-gb6wisvuia-as.a.run.app/api/health

## Brief description (≈ 250 words)

Scams are Asia-Pacific's fastest-growing financial crime - Southeast Asians lost an estimated US$23.6 billion in a
year, and in Malaysia phone scams are the #1 category. The most damaging scams succeed *during* a phone call, when
the victim is persuaded to move their own money; existing tools only block known numbers and links afterwards.

**Kawal** (Malay for “guard”) protects people at that moment. Its **Live Call Guardian** streams a speakerphone call
to **Gemini 3.8 Live**, which flags manipulation tactics (fake police, “safe account”, secrecy, OTP requests) via
function calling within about a second, while **Gemini 3.5 Flash-Lite** re-scores the transcript for a calibrated risk
meter. At high risk Kawal shows a full-screen alert, a one-tap national hotline and *speaks* a warning in the user's
language (EN / BM / 中文). **Scam Check** runs a multi-agent pipeline on messages, screenshots and voice notes:
**Gemini 3.8 Flash** returns an explainable, structured verdict; an evidence agent verifies with Google Search
grounding and Web Risk; an intel agent matches the report to known campaigns. Banks and regulators get an **Intel
Console** with Gemini-written threat bulletins and a tool-calling analyst agent.

**How we use Google:** **Cloud Run** hosts the FastAPI service (SSE agent pipeline + WebSocket bridge to Gemini
Live) under a least-privilege service account. **Firestore** stores redacted reports with a **vector index** for
campaign clustering, HMAC-fingerprinted indicators, TTL data minimisation and real-time listeners for the console.
**Firebase** provides Hosting, anonymous **Authentication** for every API call, and Security Rules (browsers are
read-only). **Gemini** (3.8 Flash, 3.8 Live, 3.5 Flash-Lite, embeddings, TTS) powers every agent. Everything is
provisioned with Terraform; no personal data or API keys are stored.

## Short description (≈ 60 words, if a shorter field is required)

Kawal is an AI guard that listens to suspicious calls in real time with Gemini 3.8 Live, warns victims in their own
language before they send money, checks messages and screenshots with a Gemini multi-agent pipeline, and turns every
check into redacted scam intelligence for banks - built on Cloud Run, Firestore (vector search), Firebase Hosting/Auth
and Gemini.
