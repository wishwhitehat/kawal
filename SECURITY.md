# Security policy

Kawal handles messages from people who may be in the middle of being defrauded, so privacy and security are
design requirements, not features. This page summarises the controls; the full threat model is in
[docs/ARCHITECTURE.md § Security model](docs/ARCHITECTURE.md#9-security-model).

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's
[private vulnerability reporting](https://github.com/wishwhitehat/kawal/security/advisories/new) for this
repository. We aim to acknowledge reports within 72 hours.

## What we store - and what we don't

| Data | Stored? | Form |
|---|---|---|
| Message text, screenshots, PDFs, voice notes | **No** | Processed in memory, sent only to Gemini on Vertex AI |
| Live call audio and transcripts | **No** | Streamed to Gemini Live; discarded after the session |
| Phone numbers, bank accounts, wallets, e-mails | Fingerprint only | HMAC-SHA256 with a secret pepper + masked label (`+6011******89`) |
| Domains of scam links | Yes | Domains are not personal data and are the most useful intel |
| Shared report | Yes, if the user opts in | Redacted English summary, tactics, type, country; **expires after 180 days** |
| Live session outcome | Yes | Verdict, peak risk, tactics, duration, redacted summary |

## Controls

- **Identity:** Firebase Authentication (anonymous) - every REST call and WebSocket carries a Firebase ID token
  verified server-side with the Firebase Admin SDK.
- **App attestation:** Firebase App Check (reCAPTCHA Enterprise) is required by the API and enforced on Firestore
  and Firebase Auth, so only the genuine web app can use the backend.
- **Abuse & cost:** per-minute limits, daily global / per-user / per-IP quotas, a budget-driven kill switch,
  upload allow-list with magic-byte sniffing and per-type size caps, output-token caps - see
  [docs/COST_CONTROLS.md](docs/COST_CONTROLS.md).
- **Transport & browser:** HTTPS only, HSTS, strict Content-Security-Policy, `X-Frame-Options: DENY`,
  `nosniff`, CORS and WebSocket `Origin` allow-lists.
- **Data access:** Firestore Security Rules allow browsers to *read* only aggregated, redacted collections
  (`campaigns`, `stats`, `feed`, `bulletins`); all writes go through the API.
- **Secrets:** no API keys or service-account keys in the codebase. Cloud Run runs as a least-privilege service
  account; the HMAC pepper lives in Secret Manager; the browser API key is restricted to our domains and to the
  Firebase APIs. Terraform state is in a private, versioned GCS bucket.
- **AI safety:** submitted content is treated as untrusted (prompt-injection guard), outputs are schema-bound and
  clamped to a fixed taxonomy, hotline numbers come from a static reviewed table, and Web Risk overrides the model
  when a link is known-malicious.

## Repository hygiene

- No credentials in the repository: `.env*`, `*.tfvars`, Terraform state, keys and credential files are git-ignored.
- History scanned with **gitleaks v8.30.1** - no leaks. A `pre-commit` hook runs gitleaks before every commit
  (`pip install pre-commit && pre-commit install`).
- GitHub secret scanning with push protection, Dependabot alerts / security updates and a ruleset that blocks
  force-pushes and deletion of `main` are enabled.
- The Firebase web API key that ships inside the built JavaScript is *public by design*; it is restricted to our
  domains and to the Firebase APIs, and is never committed.

## Supported versions

This is a hackathon prototype; only the `main` branch is maintained.
