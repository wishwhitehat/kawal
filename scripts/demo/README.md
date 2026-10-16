# Demo video & pitch-deck tooling

Reproducible build of the submission video and deck. Run from a scratch folder; nothing here needs secrets
except the **App Check debug token**, which is passed on the command line (read it from your private
`infra/terraform.tfvars`) and never written to disk.

| Script | What it does |
|---|---|
| `narrate.py <outdir>` | Voices the narration (`n1`-`n6`) with Gemini TTS (`gemini-3.8-flash-tts`, voice Charon). |
| `record.mjs <outdir> <debug-token> <n2> <n3> <n4> <n5>` | Headless Chrome (Puppeteer) records the **live production app**: Live Guardian with the BM sample call, Scam Check, Intel Console. Hooks the page to timestamp the sample audio and capture Kawal's spoken-warning PCM frames. |
| `assemble.py <outdir> <deckdir> <sample.m4a> <out.mp4>` | Mixes narration + the real call audio + Kawal's voice at their recorded times and concatenates intro slide → live → check → intel → closing slides into a 1080p H.264/AAC MP4 (~3 min). |
| `deck.html` | The pitch deck laid out on the official template pages (`bg/pNN.png` rendered from the template PDF, images from `docs/images`). |
| `deck.mjs <deckdir>` | Renders every slide to PNG, exports `deck.pdf`, and dumps element geometry to `geo.json`. |
| `build_pptx.py <deckdir> <out.pptx>` | Builds an editable PPTX from `geo.json`: template background + native text boxes, shapes and pictures. |

Requirements: Node + `puppeteer`, Python with `google-genai`, `numpy`, `pymupdf`, `python-pptx`, and `ffmpeg`.
