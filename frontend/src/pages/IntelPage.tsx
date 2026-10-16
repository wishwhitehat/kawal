import { collection, doc, limit, onSnapshot, orderBy, query } from "firebase/firestore";
import {
  Activity, ArrowDownRight, ArrowUpRight, Bot, Building2, ClipboardCopy, FileWarning, Fingerprint, Megaphone,
  Minus, Radio, Search, Send, ShieldAlert, Sparkles, TrendingUp, Wrench,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Card, FLAG, Pill, SectionTitle, Spinner } from "../components/ui";
import { askIntel, getOverview, makeBulletin } from "../lib/api";
import { ensureUser } from "../lib/firebase";
import { db } from "../lib/firestore";
import { usePrefs } from "../lib/prefs";
import { plain } from "../lib/text";
import type { Bulletin, Campaign, FeedItem, Lang, Overview } from "../lib/types";

const TYPE_LABEL: Record<string, string> = {
  authority_impersonation: "Gov / police impersonation",
  bank_impersonation: "Bank impersonation",
  parcel_courier: "Parcel / courier",
  investment: "Investment / crypto",
  job_task: "Job / task",
  romance: "Romance",
  ecommerce: "E-commerce",
  phishing: "Phishing",
  loan: "Loan",
  prize_lottery: "Prize / lottery",
  family_emergency: "Family emergency",
  tech_support: "Tech support / malware",
  deepfake_voice: "Deepfake voice",
  other: "Other",
};

const fmt = (n?: number) => new Intl.NumberFormat("en-MY").format(n ?? 0);

function ago(iso: string) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function IntelPage() {
  const { t } = usePrefs();
  const [ov, setOv] = useState<Overview | null>(null);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [liveStats, setLiveStats] = useState<Overview["stats"] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getOverview().then(setOv).catch((e) => setError(String(e.message ?? e)));
  }, []);

  // Firestore real-time listeners: the console updates the moment anyone runs a check.
  useEffect(() => {
    let unsubs: (() => void)[] = [];
    ensureUser().then(() => {
      unsubs = [
        onSnapshot(query(collection(db, "feed"), orderBy("createdAt", "desc"), limit(12)), (snap) =>
          setFeed(snap.docs.map((d) => ({ id: d.id, ...d.data(), createdAt: d.data().createdAt?.toDate?.().toISOString() ?? "" }) as FeedItem)),
        ),
        onSnapshot(doc(db, "stats", "global"), (snap) => setLiveStats((snap.data() as Overview["stats"]) ?? null)),
      ];
    });
    return () => unsubs.forEach((u) => u());
  }, []);

  const stats = liveStats ?? ov?.stats ?? {};
  const scams = stats.verdicts?.scam ?? 0;

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Pill className="mb-3 bg-brand-100 text-brand-800">
            <Building2 className="h-3.5 w-3.5" /> For banks · regulators · telcos
          </Pill>
          <h1 className="text-3xl font-extrabold tracking-tight text-brand-950">{t("intelTitle")}</h1>
          <p className="mt-2 max-w-2xl text-slate-600">{t("intelSub")}</p>
        </div>
        <Pill className="bg-amber-50 text-amber-800 ring-1 ring-amber-200">ⓘ {t("demoData")}</Pill>
      </section>

      {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">{error}</div>}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi icon={<FileWarning className="h-5 w-5" />} label={t("kpiReports")} value={fmt(stats.reports)} />
        <Kpi icon={<ShieldAlert className="h-5 w-5" />} label={t("kpiScams")} value={fmt(scams)} accent="text-red-600" />
        <Kpi icon={<Radio className="h-5 w-5" />} label={t("kpiLive")} value={fmt(stats.liveSessions)} />
        <Kpi icon={<TrendingUp className="h-5 w-5" />} label={t("kpiLoss")} value={`RM ${fmt(stats.lossAvertedMYR)}`} accent="text-emerald-700" />
      </div>

      {!ov ? (
        <div className="flex justify-center py-16 text-brand-700"><Spinner className="h-8 w-8" /></div>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="p-5 lg:col-span-2">
              <SectionTitle icon={<Activity className="h-4 w-4" />}>{t("trend")}</SectionTitle>
              <TrendChart series={ov.series} />
            </Card>
            <Card className="p-5">
              <SectionTitle icon={<Radio className="h-4 w-4" />}>{t("feed")} <span className="ml-1 inline-block h-2 w-2 rounded-full bg-emerald-500" /></SectionTitle>
              <ul className="max-h-72 space-y-2 overflow-y-auto">
                {(feed.length ? feed : ov.feed).map((f) => (
                  <li key={f.id} className="slide-in flex items-start gap-2 rounded-lg bg-slate-50 p-2.5 text-sm">
                    <span>{FLAG(f.country)}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold text-slate-800">{f.headline || TYPE_LABEL[f.scamType]}</span>
                      <span className="text-xs text-slate-500">{TYPE_LABEL[f.scamType] ?? f.scamType} · {f.source === "live" ? "📞 live call" : f.source === "seed" ? "seed" : "check"} · {f.createdAt && ago(f.createdAt)}</span>
                    </span>
                    <Pill className={f.verdict === "scam" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}>{f.riskScore}</Pill>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          <Card className="p-5">
            <SectionTitle icon={<Megaphone className="h-4 w-4" />}>{t("campaigns")}</SectionTitle>
            <div className="grid gap-3 md:grid-cols-2">
              {ov.campaigns.map((c) => <CampaignCard key={c.id} c={c} />)}
            </div>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="p-5">
              <SectionTitle icon={<Wrench className="h-4 w-4" />}>{t("tactics")}</SectionTitle>
              <BarList rows={ov.tactics.map((x) => ({ label: x.label, value: x.count }))} />
            </Card>
            <Card className="p-5">
              <SectionTitle icon={<Fingerprint className="h-4 w-4" />}>{t("indicators")}</SectionTitle>
              <ul className="space-y-2">
                {ov.indicators.map((i, k) => (
                  <li key={k} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                    <span className="font-mono text-slate-700">{i.kind} · {i.masked}</span>
                    <span className="font-semibold text-red-700">{i.count}× {Object.keys(i.countries || {}).map(FLAG).join(" ")}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-slate-500">Phone numbers and accounts are stored only as keyed HMAC fingerprints and masked labels.</p>
            </Card>
          </div>

          <BulletinPanel initial={ov.bulletin} />
          <AskPanel />
        </>
      )}
    </div>
  );
}

function Kpi({ icon, label, value, accent = "text-brand-950" }: { icon: React.ReactNode; label: string; value: string; accent?: string }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-brand-700">{icon}<span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span></div>
      <div className={`mt-2 text-2xl font-extrabold tabular-nums sm:text-3xl ${accent}`}>{value}</div>
    </Card>
  );
}

function TrendChart({ series }: { series: Overview["series"] }) {
  const max = Math.max(1, ...series.map((d) => d.scam + d.suspicious));
  const W = 640, H = 180, gap = 4;
  const bw = (W - gap * (series.length - 1)) / series.length;
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H + 18}`} className="h-auto w-full" role="img" aria-label="Daily reports, last 21 days">
        {series.map((d, i) => {
          const x = i * (bw + gap);
          const hs = (d.scam / max) * H;
          const hq = (d.suspicious / max) * H;
          return (
            <g key={d.day}>
              <title>{`${d.day}: ${d.scam} scam, ${d.suspicious} suspicious`}</title>
              <rect x={x} y={H - hs} width={bw} height={hs} rx={3} fill="#7c3aed" />
              <rect x={x} y={H - hs - hq} width={bw} height={hq} rx={3} fill="#f59e0b" opacity={0.85} />
              {i % 5 === 0 && <text x={x + bw / 2} y={H + 14} textAnchor="middle" fontSize="10" fill="#64748b">{d.day.slice(5)}</text>}
            </g>
          );
        })}
      </svg>
      <div className="mt-2 flex gap-4 text-xs text-slate-600">
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-brand-600" /> Scam</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-amber-500" /> Suspicious</span>
      </div>
    </div>
  );
}

function Spark({ data }: { data: number[] }) {
  const max = Math.max(1, ...data);
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * 100},${28 - (v / max) * 26}`).join(" ");
  return (
    <svg viewBox="0 0 100 30" className="h-8 w-28" preserveAspectRatio="none" aria-hidden>
      <polyline points={pts} fill="none" stroke="#7c3aed" strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function CampaignCard({ c }: { c: Campaign }) {
  const delta = (c.last7 ?? 0) - (c.prev7 ?? 0);
  const Trend = delta > 0 ? ArrowUpRight : delta < 0 ? ArrowDownRight : Minus;
  return (
    <div className="rounded-xl border border-brand-100 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-bold leading-snug text-brand-950">{c.title}</div>
          <div className="text-xs text-slate-500">{TYPE_LABEL[c.scamType] ?? c.scamType}</div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-extrabold tabular-nums text-brand-900">{c.count}</div>
          <div className={`flex items-center justify-end text-xs font-semibold ${delta > 0 ? "text-red-600" : delta < 0 ? "text-emerald-600" : "text-slate-500"}`}>
            <Trend className="h-3.5 w-3.5" /> {c.last7 ?? 0} / 7d
          </div>
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1">
          {Object.keys(c.countries || {}).map((cc) => <span key={cc} title={cc}>{FLAG(cc)}</span>)}
        </div>
        {c.spark && <Spark data={c.spark} />}
      </div>
      {c.summary && <p className="mt-2 line-clamp-2 text-sm text-slate-600">{c.summary}</p>}
    </div>
  );
}

function BarList({ rows }: { rows: { label: string; value: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.label}>
          <div className="mb-1 flex justify-between text-sm">
            <span className="text-slate-700">{r.label}</span>
            <span className="font-semibold tabular-nums text-slate-900">{r.value}</span>
          </div>
          <div className="h-2 rounded-full bg-brand-50">
            <div className="h-2 rounded-full bg-brand-600" style={{ width: `${(r.value / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

const LEVEL_STYLE: Record<string, string> = {
  low: "bg-emerald-100 text-emerald-800",
  elevated: "bg-amber-100 text-amber-800",
  high: "bg-orange-100 text-orange-800",
  critical: "bg-red-100 text-red-800",
};

function BulletinPanel({ initial }: { initial: Bulletin | null }) {
  const { t, lang } = usePrefs();
  const [b, setB] = useState<Bulletin | null>(initial);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<Lang>(lang);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function gen() {
    setBusy(true);
    setErr(null);
    try {
      setB(await makeBulletin());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <SectionTitle icon={<Sparkles className="h-4 w-4" />}>{t("bulletin")}</SectionTitle>
        <button onClick={gen} disabled={busy} className="inline-flex items-center gap-2 rounded-xl bg-brand-900 px-4 py-2 text-sm font-bold text-white hover:bg-brand-800 disabled:opacity-60">
          {busy ? <Spinner /> : <Sparkles className="h-4 w-4" />} {busy ? t("generating") : t("genBulletin")}
        </button>
      </div>
      {err && <p className="text-sm text-red-700">{err}</p>}
      {b && (
        <div className="slide-in space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-xl font-bold text-brand-950">{b.title}</h3>
            <Pill className={LEVEL_STYLE[b.threat_level]}>{t("threatLevel")}: {b.threat_level}</Pill>
            {b.createdAt && <span className="text-xs text-slate-500">{new Date(b.createdAt).toLocaleString()}</span>}
          </div>
          <p className="text-slate-700">{b.executive_summary}</p>
          <div className="grid gap-3 md:grid-cols-2">
            {b.campaigns.map((c, i) => (
              <div key={i} className="rounded-xl border border-brand-100 p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-bold text-brand-950">{c.name}</div>
                  <Pill className={c.trend === "rising" || c.trend === "new" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-600"}>{c.trend}</Pill>
                </div>
                <p className="mt-1 text-sm text-slate-600">{c.what_is_happening}</p>
                <div className="mt-2 text-xs font-bold uppercase text-brand-700">{t("bankControls")}</div>
                <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-slate-700">
                  {c.bank_controls.map((x, j) => <li key={j}>{x}</li>)}
                </ul>
              </div>
            ))}
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="mb-1 text-xs font-bold uppercase text-slate-600">{t("muleSignals")}</div>
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                {b.mule_signals.map((m, i) => <li key={i}>{m}</li>)}
              </ul>
            </div>
            <div className="rounded-xl bg-brand-50 p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-bold uppercase text-brand-800">{t("advisory")}</span>
                <div className="flex gap-1">
                  {(["en", "ms", "zh"] as Lang[]).map((l) => (
                    <button key={l} onClick={() => setTab(l)} className={`rounded px-2 py-0.5 text-xs font-bold ${tab === l ? "bg-brand-700 text-white" : "text-brand-800"}`}>
                      {l === "zh" ? "中文" : l.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
              <p className="text-sm text-brand-950">{b.customer_advisory[tab]}</p>
              <button
                onClick={() => {
                  void navigator.clipboard.writeText(b.customer_advisory[tab]);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                }}
                className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-brand-800"
              >
                <ClipboardCopy className="h-3.5 w-3.5" /> {copied ? t("copied") : t("copy")}
              </button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

const SUGGESTIONS = [
  "Which scam campaigns are rising this week?",
  "What tactics do Malaysian parcel scams use?",
  "Has +60 11-2345 6789 been reported?",
  "Summarise investment scams targeting Singapore.",
];

function AskPanel() {
  const { t } = usePrefs();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [ans, setAns] = useState<{ answer: string; trace: { tool: string; args: Record<string, unknown>; preview: string }[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function go(question = q) {
    if (!question.trim()) return;
    setQ(question);
    setBusy(true);
    setErr(null);
    setAns(null);
    try {
      setAns(await askIntel(question));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-5">
      <SectionTitle icon={<Bot className="h-4 w-4" />}>{t("ask")}</SectionTitle>
      <form onSubmit={(e) => (e.preventDefault(), go())} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} placeholder={t("askPlaceholder")} className="w-full rounded-xl border border-brand-100 py-2.5 pl-9 pr-3 outline-none focus:border-brand-400 focus:ring-4 focus:ring-brand-100" />
        </div>
        <button disabled={busy} className="inline-flex items-center gap-1.5 rounded-xl bg-brand-900 px-4 font-bold text-white hover:bg-brand-800 disabled:opacity-60">
          {busy ? <Spinner /> : <Send className="h-4 w-4" />} {t("askBtn")}
        </button>
      </form>
      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => go(s)} className="rounded-full border border-brand-100 px-3 py-1 text-xs hover:bg-brand-50">{s}</button>
        ))}
      </div>
      {err && <p className="mt-3 text-sm text-red-700">{err}</p>}
      {ans && (
        <div className="slide-in mt-4 space-y-3">
          <div className="whitespace-pre-wrap rounded-xl bg-brand-50/60 p-4 text-sm leading-relaxed text-slate-800">{plain(ans.answer)}</div>
          {ans.trace.length > 0 && (
            <details className="rounded-xl border border-slate-200 p-3 text-sm">
              <summary className="cursor-pointer font-semibold text-slate-700">{t("howGot")} ({ans.trace.length} tool calls)</summary>
              <ol className="mt-2 space-y-2">
                {ans.trace.map((s, i) => (
                  <li key={i} className="rounded-lg bg-slate-50 p-2 font-mono text-xs text-slate-700">
                    <span className="font-bold text-brand-800">{s.tool}</span>({JSON.stringify(s.args)})
                    <div className="mt-1 truncate text-slate-500">→ {s.preview}</div>
                  </li>
                ))}
              </ol>
            </details>
          )}
        </div>
      )}
    </Card>
  );
}
