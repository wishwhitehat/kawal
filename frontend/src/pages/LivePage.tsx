import { AlertOctagon, Bot, Mic, PhoneCall, PhoneOff, Play, Radio, ShieldAlert, ShieldCheck, Volume2, VolumeX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Card, FLAG, KillChainBar, Pill, RiskGauge, SectionTitle, Spinner, riskColor } from "../components/ui";
import { liveSocketUrl } from "../lib/api";
import { captureMic, captureSample, PcmPlayer, type Capture } from "../lib/audio";
import { idToken } from "../lib/firebase";
import { usePrefs } from "../lib/prefs";
import type { Hotline, Signal } from "../lib/types";

const SAMPLES = [
  { id: "macau-scam-ms", flag: "🇲🇾", title: "Polis palsu & 'akaun selamat'", sub: "Macau scam · Bahasa Melayu", lang: "ms" },
  { id: "bank-impersonation-en", flag: "🇸🇬", title: "Fake bank fraud team", sub: "TAC + remote app · English", lang: "en" },
  { id: "parcel-police-zh", flag: "🇨🇳", title: "快递扣留 + 假公安", sub: "Parcel & police scam · 中文", lang: "zh" },
  { id: "legit-bank-en", flag: "✅", title: "Genuine bank call", sub: "Control sample · English", lang: "en" },
] as const;

const KILL_CHAIN = [
  { id: "contact", label: "Contact" },
  { id: "hook", label: "Hook" },
  { id: "pressure", label: "Pressure" },
  { id: "extraction", label: "Money / data ask" },
  { id: "cashout", label: "Cash-out" },
];

interface Line { text: string; t: number }
interface Summary {
  verdict: string; headline: string; userMessage: string; scamTypeLabel?: string;
  maxRisk: number; signals: Signal[]; durationS: number; hotline?: Hotline;
}
type Phase = "idle" | "connecting" | "live" | "summarising" | "done";

export default function LivePage() {
  const { t, lang, country } = usePrefs();
  const [mode, setMode] = useState<"sample" | "mic">("sample");
  const [sample, setSample] = useState<string>(SAMPLES[0].id);
  const [speakOut, setSpeakOut] = useState(true);
  const [phase, setPhase] = useState<Phase>("idle");
  const [lines, setLines] = useState<Line[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [risk, setRisk] = useState(0);
  const [stage, setStage] = useState("contact");
  const [scamType, setScamType] = useState("");
  const [claims, setClaims] = useState("");
  const [kawalSaid, setKawalSaid] = useState("");
  const [alert, setAlert] = useState<{ text: string; hotline: Hotline } | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(0);

  const ws = useRef<WebSocket | null>(null);
  const cap = useRef<Capture | null>(null);
  const player = useRef<PcmPlayer | null>(null);
  const transcriptEnd = useRef<HTMLDivElement>(null);
  const speakRef = useRef(speakOut);
  speakRef.current = speakOut;

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [lines]);
  useEffect(() => () => teardown(), []);

  useEffect(() => {
    if (phase !== "live") return;
    const id = setInterval(() => setLevel(cap.current?.level() ?? 0), 80);
    return () => clearInterval(id);
  }, [phase]);

  function teardown() {
    cap.current?.stop();
    cap.current = null;
    player.current?.close();
    player.current = null;
    if (ws.current && ws.current.readyState <= 1) ws.current.close();
    ws.current = null;
  }

  async function start() {
    setError(null);
    setLines([]);
    setSignals([]);
    setRisk(0);
    setStage("contact");
    setScamType("");
    setClaims("");
    setKawalSaid("");
    setSummary(null);
    setAlert(null);
    setPhase("connecting");

    const sampleLang = SAMPLES.find((s) => s.id === sample)?.lang;
    const sessionLang = mode === "sample" && sampleLang ? sampleLang : lang;
    try {
      const token = await idToken();
      const sock = new WebSocket(liveSocketUrl());
      sock.binaryType = "arraybuffer";
      ws.current = sock;
      player.current = new PcmPlayer();

      sock.onopen = () =>
        sock.send(JSON.stringify({ type: "start", token, lang: sessionLang, country, speak: speakRef.current, share: true }));
      sock.onclose = () => {
        cap.current?.stop();
        setPhase((p) => (p === "live" || p === "connecting" ? "done" : p));
      };
      sock.onerror = () => setError("Connection to Kawal failed.");
      sock.onmessage = async (ev) => {
        if (ev.data instanceof ArrayBuffer) {
          if (speakRef.current) player.current?.play(ev.data);
          return;
        }
        const m = JSON.parse(ev.data);
        switch (m.type) {
          case "ready": {
            const send = (pcm: ArrayBuffer) => sock.readyState === 1 && sock.send(pcm);
            cap.current = mode === "mic" ? await captureMic(send) : await captureSample(`/samples/${sample}.m4a`, send);
            setPhase("live");
            cap.current.ended.then(() => setTimeout(stop, 1200));
            break;
          }
          case "transcript":
            setLines((l) => [...l, { text: m.text, t: m.t }]);
            break;
          case "signal":
            setSignals((s) => (s.some((x) => x.tactic === m.tactic) ? s : [...s, m]));
            setRisk((r) => Math.max(r, m.risk));
            break;
          case "risk":
            setRisk(m.risk);
            setStage(m.stage);
            setScamType(m.scamTypeLabel);
            if (m.claims) setClaims(m.claims);
            break;
          case "alert":
            setAlert({ text: m.text, hotline: m.hotline });
            setRisk((r) => Math.max(r, m.risk));
            if ("vibrate" in navigator) navigator.vibrate?.([300, 120, 300]);
            break;
          case "kawal_said":
            setKawalSaid(m.text);
            break;
          case "summary":
            setSummary(m);
            setPhase("done");
            break;
          case "error":
            setError(m.message);
            break;
        }
      };
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("idle");
      teardown();
    }
  }

  function stop() {
    cap.current?.stop();
    cap.current = null;
    if (ws.current?.readyState === 1) {
      ws.current.send(JSON.stringify({ type: "stop" }));
      setPhase("summarising");
    }
  }

  function toggleSpeak() {
    const v = !speakOut;
    setSpeakOut(v);
    if (ws.current?.readyState === 1) ws.current.send(JSON.stringify({ type: "speak", value: v }));
  }

  const c = riskColor(risk);
  const status = risk >= 70 ? t("statusDanger") : risk >= 40 ? t("statusWatch") : t("statusSafe");
  const active = phase === "connecting" || phase === "live" || phase === "summarising";

  return (
    <div className="space-y-6">
      <section className="mx-auto max-w-3xl text-center">
        <Pill className="mb-4 bg-brand-100 text-brand-800">
          <Radio className="h-3.5 w-3.5" /> Gemini 3.8 Live · real-time audio · function calling
        </Pill>
        <h1 className="text-3xl font-extrabold tracking-tight text-brand-950 sm:text-4xl">{t("liveTitle")}</h1>
        <p className="mx-auto mt-3 max-w-2xl text-base text-slate-600">{t("liveSub")}</p>
      </section>

      {phase === "idle" && (
        <Card className="mx-auto max-w-4xl p-4 sm:p-6">
          <div className="grid gap-3 sm:grid-cols-2">
            <button onClick={() => setMode("sample")} className={`rounded-xl border-2 p-4 text-left ${mode === "sample" ? "border-brand-600 bg-brand-50" : "border-brand-100"}`}>
              <Play className="mb-2 h-6 w-6 text-brand-700" />
              <div className="font-bold text-brand-950">{t("liveSample")}</div>
              <div className="text-sm text-slate-500">{t("liveSampleSub")}</div>
            </button>
            <button onClick={() => setMode("mic")} className={`rounded-xl border-2 p-4 text-left ${mode === "mic" ? "border-brand-600 bg-brand-50" : "border-brand-100"}`}>
              <Mic className="mb-2 h-6 w-6 text-brand-700" />
              <div className="font-bold text-brand-950">{t("liveMic")}</div>
              <div className="text-sm text-slate-500">{t("liveMicSub")}</div>
            </button>
          </div>

          {mode === "sample" && (
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {SAMPLES.map((s) => (
                <label key={s.id} className={`flex cursor-pointer items-center gap-3 rounded-xl border p-3 ${sample === s.id ? "border-brand-500 bg-brand-50/60" : "border-slate-200"}`}>
                  <input type="radio" name="sample" checked={sample === s.id} onChange={() => setSample(s.id)} className="accent-brand-700" />
                  <span className="text-2xl">{s.flag}</span>
                  <span>
                    <span className="block font-semibold text-brand-950">{s.title}</span>
                    <span className="block text-xs text-slate-500">{s.sub}</span>
                  </span>
                </label>
              ))}
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={speakOut} onChange={(e) => setSpeakOut(e.target.checked)} className="h-4 w-4 accent-brand-700" />
              {t("speakWarnings")}
            </label>
            <button onClick={start} className="ml-auto inline-flex items-center gap-2 rounded-xl bg-brand-900 px-6 py-3 text-base font-bold text-white shadow-lg shadow-brand-900/20 hover:bg-brand-800">
              <PhoneCall className="h-5 w-5" /> {t("start")}
            </button>
          </div>
          {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
        </Card>
      )}

      {(active || phase === "done") && (
        <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
          <Card className="flex flex-col items-center gap-4 p-5">
            <div className="flex w-full items-center justify-between">
              <span className={`relative inline-flex items-center gap-2 text-sm font-bold ${phase === "live" ? "text-red-600" : "text-slate-500"}`}>
                {phase === "live" && <span className="pulse-ring relative h-2.5 w-2.5 rounded-full bg-red-600 text-red-500" />}
                {phase === "connecting" ? t("connecting") : phase === "live" ? t("listening") : phase === "summarising" ? "…" : t("summaryTitle")}
              </span>
              <button onClick={toggleSpeak} title={t("speakWarnings")} className="rounded-lg border border-brand-100 p-1.5 text-brand-800">
                {speakOut ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
              </button>
            </div>
            <RiskGauge value={risk} size={230} label={t("risk")} />
            <div className={`rounded-full px-4 py-1.5 text-sm font-bold ${c.soft} ${c.text}`}>{status}</div>
            {scamType && <div className="text-center text-sm font-semibold text-slate-700">{scamType}</div>}
            {claims && (
              <div className="w-full rounded-xl bg-slate-50 p-3 text-sm">
                <div className="text-xs font-semibold uppercase text-slate-500">{t("callerClaims")}</div>
                <div className="font-semibold text-slate-800">🎭 {claims}</div>
              </div>
            )}
            <div className="w-full">
              <KillChainBar stages={KILL_CHAIN} current={stage} />
            </div>
            {phase === "live" && (
              <div className="flex h-8 w-full items-end gap-0.5" aria-hidden>
                {Array.from({ length: 28 }).map((_, i) => (
                  <div key={i} className="flex-1 rounded-sm bg-brand-400" style={{ height: `${Math.max(8, Math.min(100, level * 260 * (0.5 + Math.abs(Math.sin(i * 1.7 + Date.now() / 300)))))}%` }} />
                ))}
              </div>
            )}
            {(phase === "live" || phase === "connecting") && (
              <button onClick={stop} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-5 py-3 font-bold text-white hover:bg-red-700">
                <PhoneOff className="h-5 w-5" /> {t("stop")}
              </button>
            )}
            {phase === "summarising" && <Spinner className="h-6 w-6 text-brand-700" />}
          </Card>

          <div className="grid gap-4">
            <Card className="p-5">
              <SectionTitle icon={<ShieldAlert className="h-4 w-4" />}>{t("signals")}</SectionTitle>
              {signals.length === 0 ? (
                <p className="text-sm text-slate-500">{t("noSignals")}</p>
              ) : (
                <ul className="grid gap-2 sm:grid-cols-2">
                  {signals.map((s) => (
                    <li key={s.tactic} className="slide-in rounded-xl border border-red-100 bg-red-50/70 p-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-bold text-red-800">{s.label}</span>
                        <span className="text-[11px] tabular-nums text-slate-500">{s.t.toFixed(0)}s · {s.by === "live" ? "Live" : "Flash-Lite"}</span>
                      </div>
                      {s.evidence && <div className="mt-1 text-sm italic text-slate-700">“{s.evidence}”</div>}
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            {kawalSaid && (
              <div className="slide-in flex items-start gap-3 rounded-2xl bg-brand-900 p-4 text-white">
                <Bot className="mt-0.5 h-5 w-5 shrink-0" />
                <div>
                  <div className="text-xs font-semibold uppercase opacity-70">{t("kawalSaid")}</div>
                  <div className="font-semibold">{kawalSaid}</div>
                </div>
              </div>
            )}

            <Card className="p-5">
              <SectionTitle icon={<Radio className="h-4 w-4" />}>{t("transcript")}</SectionTitle>
              <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                {lines.map((l, i) => (
                  <p key={i} className="slide-in text-sm leading-relaxed text-slate-700">
                    <span className="mr-2 text-[11px] tabular-nums text-slate-400">{l.t.toFixed(0)}s</span>
                    {l.text}
                  </p>
                ))}
                {phase === "live" && lines.length === 0 && <p className="text-sm text-slate-400">{t("listening")}</p>}
                <div ref={transcriptEnd} />
              </div>
            </Card>

            {summary && (
              <Card className="slide-in p-5">
                <SectionTitle icon={summary.verdict === "likely_safe" ? <ShieldCheck className="h-4 w-4" /> : <AlertOctagon className="h-4 w-4" />}>
                  {t("summaryTitle")}
                </SectionTitle>
                <h3 className="text-lg font-bold text-brand-950">{summary.headline}</h3>
                <p className="mt-1 text-slate-700">{summary.userMessage}</p>
                <div className="mt-3 flex flex-wrap gap-2 text-sm">
                  <Pill className="bg-slate-100 text-slate-700">{t("peakRisk")}: {summary.maxRisk}</Pill>
                  <Pill className="bg-slate-100 text-slate-700">{t("duration")}: {summary.durationS}s</Pill>
                  {summary.scamTypeLabel && <Pill className="bg-slate-100 text-slate-700">{summary.scamTypeLabel}</Pill>}
                </div>
                <button onClick={() => setPhase("idle")} className="mt-4 rounded-lg border border-brand-200 px-4 py-2 text-sm font-semibold text-brand-900 hover:bg-brand-50">
                  ← {t("liveSample")}
                </button>
              </Card>
            )}
            {error && <p className="text-sm text-red-700">{error}</p>}
          </div>
        </div>
      )}

      {alert && (
        <div role="alertdialog" aria-modal="true" className="alert-flash fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-3xl bg-white p-6 text-center shadow-2xl sm:p-8">
            <AlertOctagon className="mx-auto h-16 w-16 text-red-600" />
            <h2 className="mt-3 text-2xl font-extrabold text-red-700 sm:text-3xl">{t("alertTitle")}</h2>
            <p className="mt-3 text-lg font-semibold text-slate-800">{t("alertDo")}</p>
            {alert.text && <p className="mt-2 text-base text-slate-600">{alert.text}</p>}
            <a href={`tel:${alert.hotline.tel}`} className="mt-5 flex items-center justify-center gap-2 rounded-2xl bg-red-600 px-5 py-4 text-lg font-extrabold text-white hover:bg-red-700">
              <PhoneCall className="h-6 w-6" /> {FLAG(alert.hotline.country)} {t("call")} {alert.hotline.primary}
            </a>
            <button onClick={() => setAlert(null)} className="mt-3 w-full rounded-2xl border border-slate-200 px-5 py-3 font-semibold text-slate-700 hover:bg-slate-50">
              {t("dismiss")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
