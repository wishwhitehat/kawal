import {
  AlertTriangle, ArrowRight, Ban, CheckCircle2, CircleDashed, Globe, Image as ImageIcon, Link2, Mic,
  Network, Phone, RotateCcw, ShieldCheck, Sparkles, Users, Volume2, X, XCircle,
} from "lucide-react";
import { useRef, useState } from "react";
import { Card, FLAG, KillChainBar, Pill, RiskGauge, SectionTitle, Spinner, VERDICT_STYLE } from "../components/ui";
import { runCheck, speak } from "../lib/api";
import { usePrefs } from "../lib/prefs";
import { plain } from "../lib/text";
import type { CheckResult, StageEvent } from "../lib/types";

const EXAMPLES = [
  {
    label: "🇲🇾 LHDN refund SMS",
    text: "LHDN: Tahniah! Anda layak menerima bayaran balik cukai RM1,286.50. Sila kemas kini maklumat akaun bank anda dalam masa 24 jam di https://lhdn-refund-claim.xyz/semak untuk mengelakkan pembatalan.",
  },
  {
    label: "💼 Part-time 'like' job",
    text: "Hi! I'm Jessica from Shopee Marketing HR 😊 We are hiring part-time staff to like products online, earn RM300-RM800 per day! Just pay RM50 registration fee to activate your task account. WhatsApp me at +60 11-2345 6789 now, only 5 slots left today!",
  },
  {
    label: "📦 顺丰 parcel fee",
    text: "【顺丰速运】您的包裹因地址不详无法派送，请于24小时内访问 sf-redelivery-my.top 更新地址并支付 RM3.50 重新派送费，逾期将退回寄件人。",
  },
  {
    label: "✅ Real bank alert",
    text: "YourBank: A card transaction of RM58.90 at GRAB*FOOD was made on 16/10 14:22. If this was not you, call the number on the back of your card. We will never ask for your PIN, password or TAC.",
  },
];

const STAGES = ["triage", "evidence", "intel", "advice"] as const;
type StageMap = Partial<Record<(typeof STAGES)[number], StageEvent>>;

export default function CheckPage() {
  const { t, lang, country } = usePrefs();
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [share, setShare] = useState(true);
  const [busy, setBusy] = useState(false);
  const [stages, setStages] = useState<StageMap>({});
  const [result, setResult] = useState<CheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const imgRef = useRef<HTMLInputElement>(null);
  const audRef = useRef<HTMLInputElement>(null);

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    setFiles((f) => [...f, ...Array.from(list)].slice(0, 3));
  };

  async function submit() {
    if (!text.trim() && !files.length) return;
    setBusy(true);
    setError(null);
    setResult(null);
    setStages({});
    const form = new FormData();
    form.append("text", text);
    form.append("lang", lang);
    form.append("country", country);
    form.append("share", String(share));
    files.forEach((f) => form.append("files", f));
    try {
      const r = await runCheck(form, (e) => setStages((s) => ({ ...s, [e.id]: e })));
      setResult(r);
      setTimeout(() => document.getElementById("result")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("errorTry"));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setText("");
    setFiles([]);
    setResult(null);
    setStages({});
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="space-y-8">
      <section className="mx-auto max-w-3xl text-center">
        <Pill className="mb-4 bg-brand-100 text-brand-800">
          <Sparkles className="h-3.5 w-3.5" /> Gemini 3.8 · multimodal · EN / BM / 中文
        </Pill>
        <h1 className="text-3xl font-extrabold tracking-tight text-brand-950 sm:text-4xl">{t("checkTitle")}</h1>
        <p className="mx-auto mt-3 max-w-2xl text-base text-slate-600">{t("checkSub")}</p>
      </section>

      <Card className="mx-auto max-w-3xl p-4 sm:p-6">
        <label htmlFor="msg" className="sr-only">{t("placeholder")}</label>
        <textarea
          id="msg"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          maxLength={4000}
          placeholder={t("placeholder")}
          className="w-full resize-y rounded-xl border border-brand-100 bg-brand-50/40 p-4 text-base outline-none placeholder:text-slate-400 focus:border-brand-400 focus:ring-4 focus:ring-brand-100"
        />

        {files.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {files.map((f, i) => (
              <span key={i} className="inline-flex items-center gap-2 rounded-lg bg-brand-50 px-3 py-1.5 text-sm text-brand-900">
                {f.type.startsWith("image") ? <ImageIcon className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                <span className="max-w-[180px] truncate">{f.name}</span>
                <button onClick={() => setFiles(files.filter((_, j) => j !== i))} aria-label="Remove file">
                  <X className="h-4 w-4" />
                </button>
              </span>
            ))}
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input ref={imgRef} type="file" accept="image/*,application/pdf" hidden multiple onChange={(e) => addFiles(e.target.files)} />
          <input ref={audRef} type="file" accept="audio/*" hidden onChange={(e) => addFiles(e.target.files)} />
          <button onClick={() => imgRef.current?.click()} className="inline-flex items-center gap-1.5 rounded-lg border border-brand-100 px-3 py-2 text-sm font-semibold text-brand-800 hover:bg-brand-50">
            <ImageIcon className="h-4 w-4" /> {t("attachImage")}
          </button>
          <button onClick={() => audRef.current?.click()} className="inline-flex items-center gap-1.5 rounded-lg border border-brand-100 px-3 py-2 text-sm font-semibold text-brand-800 hover:bg-brand-50">
            <Mic className="h-4 w-4" /> {t("attachAudio")}
          </button>
          <label className="ml-auto flex cursor-pointer items-center gap-2 text-sm text-slate-600" title={t("shareHint")}>
            <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} className="h-4 w-4 accent-brand-700" />
            {t("share")}
          </label>
        </div>

        <button
          onClick={submit}
          disabled={busy || (!text.trim() && !files.length)}
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-brand-900 px-6 py-3.5 text-base font-bold text-white shadow-lg shadow-brand-900/20 transition hover:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? <Spinner /> : <ShieldCheck className="h-5 w-5" />}
          {busy ? t("checking") : t("checkBtn")}
        </button>

        <div className="mt-4">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{t("examples")}</div>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button key={ex.label} onClick={() => setText(ex.text)} className="rounded-full border border-brand-100 bg-white px-3 py-1.5 text-sm hover:border-brand-300 hover:bg-brand-50">
                {ex.label}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {(busy || Object.keys(stages).length > 0) && !result && <AgentTimeline stages={stages} />}
      {error && (
        <div className="mx-auto max-w-3xl rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">{error}</div>
      )}
      {result && <ResultView r={result} stages={stages} onReset={reset} />}
    </div>
  );
}

function AgentTimeline({ stages }: { stages: StageMap }) {
  const { t } = usePrefs();
  const meta = {
    triage: [t("stageTriage"), t("stageTriageSub"), Sparkles],
    evidence: [t("stageEvidence"), t("stageEvidenceSub"), Globe],
    intel: [t("stageIntel"), t("stageIntelSub"), Network],
    advice: [t("stageAdvice"), t("stageAdviceSub"), Phone],
  } as const;
  return (
    <Card className="mx-auto max-w-3xl p-4 sm:p-5">
      <ol className="grid gap-3 sm:grid-cols-4">
        {STAGES.map((id) => {
          const s = stages[id];
          const [title, sub, Icon] = meta[id];
          return (
            <li key={id} className={`rounded-xl border p-3 ${s?.status === "done" ? "border-emerald-200 bg-emerald-50/50" : s?.status === "running" ? "border-brand-300 bg-brand-50" : "border-slate-100"}`}>
              <div className="flex items-center gap-2">
                {s?.status === "done" ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : s?.status === "running" ? <Spinner className="h-4 w-4 text-brand-700" /> : s?.status === "error" ? <XCircle className="h-4 w-4 text-slate-400" /> : <CircleDashed className="h-4 w-4 text-slate-300" />}
                <Icon className="h-4 w-4 text-brand-700" />
                {s?.ms !== undefined && s.status === "done" && s.ms > 0 && <span className="ml-auto text-[11px] tabular-nums text-slate-500">{(s.ms / 1000).toFixed(1)}s</span>}
              </div>
              <div className="mt-1.5 text-sm font-bold text-brand-950">{title}</div>
              <div className="text-xs text-slate-500">{sub}</div>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

function ResultView({ r, stages, onReset }: { r: CheckResult; stages: StageMap; onReset: () => void }) {
  const { t, lang } = usePrefs();
  const [speaking, setSpeaking] = useState(false);
  const style = VERDICT_STYLE[r.verdict];
  const verdictLabel = t(`verdict_${r.verdict}` as const);

  async function readAloud() {
    setSpeaking(true);
    try {
      const audio = await speak(`${verdictLabel}. ${r.headline}. ${r.explanation} ${r.doNow.join(". ")}`, lang);
      audio.onended = () => setSpeaking(false);
    } catch {
      setSpeaking(false);
    }
  }

  return (
    <div id="result" className="mx-auto max-w-5xl scroll-mt-24 space-y-4 slide-in">
      <AgentTimeline stages={stages} />

      <Card className="overflow-hidden">
        <div className={`bg-gradient-to-r ${style.band} px-5 py-4 text-white sm:px-7`}>
          <div className="flex flex-wrap items-center gap-3">
            {r.verdict === "likely_safe" ? <ShieldCheck className="h-7 w-7" /> : <AlertTriangle className="h-7 w-7" />}
            <span className="text-2xl font-extrabold uppercase tracking-wide">{verdictLabel}</span>
            <span className="rounded-full bg-white/20 px-3 py-1 text-sm font-semibold">{r.scamTypeLabel}</span>
            <button onClick={readAloud} disabled={speaking} className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-white/15 px-3 py-1.5 text-sm font-semibold hover:bg-white/25">
              {speaking ? <Spinner /> : <Volume2 className="h-4 w-4" />} {t("readAloud")}
            </button>
          </div>
        </div>
        <div className="grid gap-6 p-5 sm:p-7 md:grid-cols-[200px_1fr]">
          <div className="flex flex-col items-center gap-2">
            <RiskGauge value={r.riskScore} label={t("risk")} />
            {r.impersonated && <Pill className="bg-slate-100 text-slate-700">🎭 {r.impersonated}</Pill>}
          </div>
          <div>
            <h2 className="text-xl font-bold text-brand-950 sm:text-2xl">{r.headline}</h2>
            <p className="mt-2 text-base leading-relaxed text-slate-700">{r.explanation}</p>
            {r.verdict !== "likely_safe" && (
              <div className="mt-5">
                <SectionTitle>{t("killChain")}</SectionTitle>
                <KillChainBar stages={r.killChain.stages} current={r.killChain.current} />
              </div>
            )}
          </div>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        {r.redFlags.length > 0 && (
          <Card className="p-5">
            <SectionTitle icon={<AlertTriangle className="h-4 w-4" />}>{t("redFlags")}</SectionTitle>
            <ul className="space-y-3">
              {r.redFlags.map((f, i) => (
                <li key={i} className="rounded-xl bg-red-50/60 p-3">
                  <div className="text-sm font-bold text-red-800">{f.label}</div>
                  <blockquote className="mt-1 border-l-2 border-red-300 pl-2 text-sm italic text-slate-700">“{f.evidence}”</blockquote>
                  <p className="mt-1 text-sm text-slate-600">{f.why}</p>
                </li>
              ))}
            </ul>
          </Card>
        )}

        <Card className="p-5">
          <SectionTitle icon={<Phone className="h-4 w-4" />}>{t("doNow")}</SectionTitle>
          {r.verdict !== "likely_safe" && (
            <a href={`tel:${r.hotline.tel}`} className="mb-3 flex items-center justify-between rounded-xl bg-brand-900 px-4 py-3 text-white hover:bg-brand-800">
              <span>
                <span className="block text-xs opacity-80">{FLAG(r.hotline.country)} {r.hotline.name}</span>
                <span className="text-lg font-extrabold">{t("call")} {r.hotline.primary}</span>
              </span>
              <Phone className="h-6 w-6" />
            </a>
          )}
          <ol className="space-y-2">
            {r.doNow.map((d, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-700">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-800">{i + 1}</span>
                {d}
              </li>
            ))}
          </ol>
          {r.dont.length > 0 && (
            <div className="mt-4">
              <div className="mb-1.5 text-xs font-bold uppercase tracking-wide text-red-700">{t("dont")}</div>
              <ul className="space-y-1.5">
                {r.dont.map((d, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-700">
                    <Ban className="mt-0.5 h-4 w-4 shrink-0 text-red-500" /> {d}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <SectionTitle icon={<Globe className="h-4 w-4" />}>{t("evidence")}</SectionTitle>
          {r.evidence.webRisk.length > 0 && (
            <div className="mb-3 rounded-xl bg-red-600 p-3 text-sm font-semibold text-white">
              ⚠ {t("webRiskHit")}: {r.evidence.webRisk.map((w) => w.domain).join(", ")}
            </div>
          )}
          {r.evidence.findings ? (
            <div className="space-y-1.5 text-sm leading-relaxed text-slate-700">
              {r.evidence.findings.split("\n").filter(Boolean).map((line, i) => (
                <p key={i}>{plain(line.replace(/^[-*•]\s*/, "• "))}</p>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500">—</p>
          )}
          {r.evidence.sources.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {r.evidence.sources.map((s, i) => (
                <a key={i} href={s.uri} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-700 hover:bg-slate-200">
                  <Link2 className="h-3 w-3" /> {s.title}
                </a>
              ))}
            </div>
          )}
        </Card>

        <Card className="p-5">
          <SectionTitle icon={<Users className="h-4 w-4" />}>{t("community")}</SectionTitle>
          {r.community.campaign && (
            <div className="mb-3 rounded-xl border border-brand-200 bg-brand-50 p-3">
              {r.community.campaign.new ? (
                <div className="text-sm font-semibold text-brand-900">✨ {t("campaignNew")}</div>
              ) : (
                <>
                  <div className="text-xs font-semibold uppercase text-brand-700">{t("campaignPart")}</div>
                  <div className="text-base font-bold text-brand-950">{r.community.campaign.title}</div>
                  <div className="text-sm text-brand-800">{r.community.campaign.count} {t("reports")}</div>
                </>
              )}
            </div>
          )}
          {r.community.repeatIndicators.length > 0 && (
            <ul className="mb-3 space-y-1.5">
              {r.community.repeatIndicators.map((ind, i) => (
                <li key={i} className="flex items-center justify-between rounded-lg bg-red-50 px-3 py-2 text-sm">
                  <span className="font-mono text-slate-800">{ind.masked}</span>
                  <span className="font-semibold text-red-700">
                    {t("reportedTimes", { n: ind.count })} {Object.keys(ind.countries || {}).map(FLAG).join(" ")}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {r.indicators.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {r.indicators.map((ind, i) => (
                <Pill key={i} className="bg-slate-100 font-mono text-slate-700">{ind.kind}: {ind.masked}</Pill>
              ))}
            </div>
          )}
          {r.shared && <p className="mt-3 text-sm text-emerald-700">✓ {t("sharedOk")}</p>}
        </Card>
      </div>

      {r.extractedText && (
        <Card className="p-5">
          <SectionTitle>{t("whatKawalRead")}</SectionTitle>
          <p className="whitespace-pre-wrap text-sm text-slate-600">{r.extractedText}</p>
        </Card>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
        <span>{r.model?.model} · {(r.timingMs / 1000).toFixed(1)}s end-to-end</span>
        <button onClick={onReset} className="inline-flex items-center gap-1.5 rounded-lg border border-brand-200 bg-white px-4 py-2 text-sm font-semibold text-brand-900 hover:bg-brand-50">
          <RotateCcw className="h-4 w-4" /> {t("checkAnother")} <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
