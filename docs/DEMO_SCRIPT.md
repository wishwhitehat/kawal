# Demo video script (target 3:00)

The rules conflict slightly (FAQ: “under 3 minutes”; submission page: “3 to 4 minutes”), so aim for **2:55-3:00**.
Record at 1440×900 or 1920×1080 in Chrome, system audio ON (the sample call and Kawal's voice must be audible).
Use **https://kawal-ai.web.app**. Do one dry run first so Firebase sign-in and Cloud Run are warm.

| Time | On screen | Voice-over (suggested) |
|---|---|---|
| **0:00-0:20** | Title card (logo + “Kawal - the AI that sits on the call with you”), then the stat slide | “Last year Malaysians lost over 2.7 billion ringgit to scams, and phone scams were the number-one category. In Singapore, 82% of losses were transfers victims made themselves - while a scammer was talking to them. Existing tools block known numbers and links. Nothing helps you *during* the call. That's Kawal - ‘guard’ in Malay.” |
| **0:20-1:25** | **Live Call Guardian** → *Try a sample scam call* → 🇲🇾 “Polis palsu & akaun selamat” → **Start guarding**. Let it play. | “I put a suspicious call on speaker. Kawal streams the audio to **Gemini 3.8 Live** on Cloud Run. Watch: the caller claims to be from Bukit Aman - Kawal flags *authority impersonation* in under a second. Money-laundering accusation - *threat*. ‘Don't tell your family’ - *secrecy*. The risk meter crosses 70…” → **alert appears** → “…full-screen alert, one tap to call NSRC 997, and Kawal *speaks* a warning in Bahasa Melayu.” (let the spoken warning play) “Then the ask: move your savings to a ‘safe account’ at Bank Negara - risk 98. A second model, Flash-Lite, re-scores the transcript every few seconds, which is why the genuine bank call in our tests got zero alerts.” |
| **1:25-1:35** | Call summary card | “When the call ends, Kawal summarises it - and stores only a redacted pattern. Never audio, never the transcript.” |
| **1:35-2:15** | **Scam Check** → click **🇲🇾 LHDN refund SMS** example (or upload a screenshot) → **Check with Kawal**; show the 4 agent cards completing, then scroll the result. | “Messages and screenshots go through a multi-agent pipeline. Gemini 3.8 Flash reads text, images or voice notes and returns a structured verdict. In parallel, an evidence agent verifies with **Google Search grounding** and **Web Risk**, and a community-intel agent searches **Firestore vector search**. Result: scam, 98, the exact red-flag quotes, where you are in the scam, official sources - and this pattern has been reported before and belongs to a known campaign.” Optionally switch to **中文** and run the 顺丰 example (5 s) to show multilingual output. |
| **2:15-2:45** | **Intel Console**: KPIs → trend → campaigns → live feed (point out your own check appearing) → **Generate bulletin with Gemini** → scroll bank controls + EN/BM/中文 advisory → **Ask Kawal Intel**: “Has +60 11-2345 6789 been reported?” → expand tool trace. | “Every check becomes intelligence for banks and regulators - updated in real time through Firestore listeners. Similar reports are clustered into campaigns with Gemini embeddings. One click and Gemini writes a threat bulletin: concrete bank controls like step-up checks when a customer is on an active call, mule-account signals, and ready-to-send advisories in three languages. Analysts can ask questions, and the agent answers by calling Firestore tools - with a full audit trail.” |
| **2:45-3:00** | Architecture slide (docs/images/architecture.png) → end card with URL + GitHub | “Kawal runs on **Cloud Run**, **Firestore**, **Firebase** Hosting, Auth and Rules, and **Gemini** 3.8 Flash, Live, Flash-Lite, embeddings and TTS - all deployed with Terraform, no API keys, no personal data stored. Built in JAPAC, for the world. Thank you.” |

**Recording tips**

- Close other tabs; turn notifications off; zoom the browser to 110 % so text is readable on video.
- If the room is noisy, use the sample call (it streams the audio directly - no microphone needed).
- To show the microphone mode, play one of the `frontend/public/samples/*.m4a` files from a phone held near the
  laptop, with **Guard a real call** selected.
- Upload to YouTube as **Unlisted** (or Google Drive “Anyone with the link”) and test the link in a private window.
