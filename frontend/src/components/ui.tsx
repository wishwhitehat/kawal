import type { ReactNode } from "react";
import type { Verdict } from "../lib/types";

export const COUNTRIES: Record<string, string> = {
  MY: "🇲🇾 Malaysia",
  SG: "🇸🇬 Singapore",
  ID: "🇮🇩 Indonesia",
  PH: "🇵🇭 Philippines",
  TH: "🇹🇭 Thailand",
  VN: "🇻🇳 Vietnam",
  AU: "🇦🇺 Australia",
  IN: "🇮🇳 India",
  HK: "🇭🇰 Hong Kong",
  TW: "🇹🇼 Taiwan",
  JP: "🇯🇵 Japan",
  KR: "🇰🇷 Korea",
};

export const FLAG = (cc: string) => COUNTRIES[cc]?.split(" ")[0] ?? "🌏";

export function riskColor(risk: number) {
  if (risk >= 70) return { text: "text-red-600", bg: "bg-red-600", soft: "bg-red-50", ring: "ring-red-200", hex: "#dc2626" };
  if (risk >= 40) return { text: "text-amber-600", bg: "bg-amber-500", soft: "bg-amber-50", ring: "ring-amber-200", hex: "#d97706" };
  return { text: "text-emerald-600", bg: "bg-emerald-600", soft: "bg-emerald-50", ring: "ring-emerald-200", hex: "#059669" };
}

export const VERDICT_STYLE: Record<Verdict, { band: string; chip: string }> = {
  scam: { band: "from-red-600 to-rose-700", chip: "bg-red-100 text-red-800" },
  suspicious: { band: "from-amber-500 to-orange-600", chip: "bg-amber-100 text-amber-800" },
  likely_safe: { band: "from-emerald-600 to-teal-700", chip: "bg-emerald-100 text-emerald-800" },
};

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-brand-100 bg-white shadow-[0_1px_2px_rgba(76,29,149,0.04),0_8px_24px_-12px_rgba(76,29,149,0.12)] ${className}`}>
      {children}
    </div>
  );
}

export function SectionTitle({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return (
    <h3 className="mb-3 flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-brand-900/70">
      {icon}
      {children}
    </h3>
  );
}

export function Pill({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${className}`}>{children}</span>;
}

/** Semi-circular risk gauge. */
export function RiskGauge({ value, size = 180, label }: { value: number; size?: number; label?: string }) {
  const v = Math.max(0, Math.min(100, value));
  const r = 70;
  const circ = Math.PI * r;
  const c = riskColor(v);
  return (
    <div className="relative inline-flex flex-col items-center" style={{ width: size }}>
      <svg viewBox="0 0 180 100" width={size} role="img" aria-label={`${label ?? "Risk"} ${v} of 100`}>
        <path d="M20 90 A70 70 0 0 1 160 90" fill="none" stroke="#ede9fe" strokeWidth="16" strokeLinecap="round" />
        <path
          d="M20 90 A70 70 0 0 1 160 90"
          fill="none"
          stroke={c.hex}
          strokeWidth="16"
          strokeLinecap="round"
          strokeDasharray={`${(v / 100) * circ} ${circ}`}
          style={{ transition: "stroke-dasharray 0.6s ease, stroke 0.6s ease" }}
        />
      </svg>
      <div className="absolute bottom-0 flex flex-col items-center leading-none">
        <span className={`text-4xl font-extrabold tabular-nums ${c.text}`}>{v}</span>
        {label && <span className="mt-1 text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</span>}
      </div>
    </div>
  );
}

export function KillChainBar({ stages, current }: { stages: { id: string; label: string }[]; current: string }) {
  const idx = stages.findIndex((s) => s.id === current);
  return (
    <ol className="grid grid-cols-5 gap-1.5">
      {stages.map((s, i) => {
        const active = i <= idx;
        const now = i === idx;
        return (
          <li key={s.id} className="flex flex-col gap-1.5">
            <div className={`h-2 rounded-full ${active ? (now ? "bg-red-500" : "bg-red-300") : "bg-slate-200"}`} />
            <span className={`text-[11px] leading-tight ${now ? "font-bold text-red-700" : active ? "text-slate-700" : "text-slate-400"}`}>
              {s.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return <span className={`inline-block animate-spin rounded-full border-2 border-current border-r-transparent ${className}`} />;
}

export function Logo({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden>
      <defs>
        <linearGradient id="kg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#8b5cf6" />
          <stop offset="1" stopColor="#4c1d95" />
        </linearGradient>
      </defs>
      <path d="M32 4 8 13v17c0 15 10.4 26.6 24 30 13.6-3.4 24-15 24-30V13L32 4Z" fill="url(#kg)" />
      <path d="M20 33h4l3-8 5 16 4-12 3 4h5" fill="none" stroke="#fff" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
