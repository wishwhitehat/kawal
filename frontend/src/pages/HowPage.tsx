import { Cloud, Code2, Database, Flame, Lock, Radio, ShieldCheck, Sparkles } from "lucide-react";
import { Card, Pill } from "../components/ui";

const STACK = [
  { icon: Sparkles, name: "Gemini 3.8 Flash", what: "Multimodal triage of text, screenshots, PDFs and voice notes with structured output; Google Search grounding; bulletin writing; tool-calling analyst agent." },
  { icon: Radio, name: "Gemini 3.8 Live", what: "Hears the call audio in real time, flags tactics via function calling and speaks a one-line warning in the user's language." },
  { icon: Sparkles, name: "Gemini 3.5 Flash-Lite · Embeddings · TTS", what: "Flash-Lite re-scores the live transcript every few seconds; gemini-embedding-2 clusters reports into campaigns; Gemini TTS reads verdicts aloud and voiced our sample calls." },
  { icon: Cloud, name: "Cloud Run", what: "FastAPI service: SSE streaming for the agent pipeline and a WebSocket bridge to Gemini Live. Runs as a least-privilege service account - no API keys." },
  { icon: Database, name: "Firestore", what: "Redacted reports, HMAC-fingerprinted indicators, vector index (KNN) for campaign clustering, real-time listeners for the console, TTL for data minimisation." },
  { icon: Flame, name: "Firebase", what: "Hosting for the web app, Authentication (anonymous sign-in) for every API call, Security Rules that make all browser access read-only." },
];

const PRIVACY = [
  "Messages, screenshots, audio and call transcripts are never stored.",
  "Phone numbers, accounts and wallets are kept only as keyed HMAC fingerprints + masked labels.",
  "Shared reports are redacted summaries and expire after 180 days (Firestore TTL).",
  "Browsers can only read aggregated, redacted collections (Firebase Security Rules).",
];

export default function HowPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <section className="text-center">
        <h1 className="text-3xl font-extrabold tracking-tight text-brand-950">How Kawal works</h1>
        <p className="mx-auto mt-3 max-w-2xl text-slate-600">
          Kawal (Malay/Indonesian for “guard”) protects people at the exact moment scams succeed - while they are
          being persuaded - and turns every check into intelligence that helps banks stop the next victim.
        </p>
      </section>

      <Card className="p-6">
        <ol className="grid gap-4 sm:grid-cols-3">
          {[
            ["1 · Check or listen", "Citizens paste a message, upload a screenshot or let Kawal listen to a call on speaker."],
            ["2 · Explain & act", "Gemini agents assess, verify with Google Search and Web Risk, and give a calm action plan with the right hotline."],
            ["3 · Protect others", "A redacted pattern joins Firestore; similar reports cluster into campaigns that banks and regulators can act on."],
          ].map(([h, p]) => (
            <li key={h} className="rounded-xl bg-brand-50 p-4">
              <div className="font-bold text-brand-950">{h}</div>
              <p className="mt-1 text-sm text-slate-600">{p}</p>
            </li>
          ))}
        </ol>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2">
        {STACK.map(({ icon: Icon, name, what }) => (
          <Card key={name} className="p-5">
            <div className="flex items-center gap-2 font-bold text-brand-950">
              <Icon className="h-5 w-5 text-brand-700" /> {name}
            </div>
            <p className="mt-1.5 text-sm text-slate-600">{what}</p>
          </Card>
        ))}
      </div>

      <Card className="p-6">
        <div className="mb-3 flex items-center gap-2 font-bold text-brand-950">
          <Lock className="h-5 w-5 text-brand-700" /> Privacy by design
        </div>
        <ul className="space-y-2">
          {PRIVACY.map((p) => (
            <li key={p} className="flex gap-2 text-sm text-slate-700">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /> {p}
            </li>
          ))}
        </ul>
      </Card>

      <div className="flex flex-wrap items-center justify-center gap-3">
        <a href="https://github.com/wishwhitehat/kawal" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-xl bg-brand-950 px-4 py-2.5 text-sm font-bold text-white">
          <Code2 className="h-4 w-4" /> Source code & architecture
        </a>
        <Pill className="bg-amber-50 text-amber-800 ring-1 ring-amber-200">
          Prototype: advice is informational - always confirm with your bank or the official hotline.
        </Pill>
      </div>
    </div>
  );
}
