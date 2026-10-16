export type Lang = "en" | "ms" | "zh";
export type Verdict = "scam" | "suspicious" | "likely_safe";

export interface RedFlag {
  tactic: string;
  label: string;
  evidence: string;
  why: string;
}

export interface Hotline {
  country: string;
  name: string;
  primary: string;
  tel: string;
  steps: string[];
}

export interface CheckResult {
  verdict: Verdict;
  riskScore: number;
  confidence?: number;
  scamType: string;
  scamTypeLabel: string;
  channel: string;
  headline: string;
  explanation: string;
  redFlags: RedFlag[];
  killChain: { stages: { id: string; label: string }[]; current: string };
  impersonated: string;
  indicators: { kind: string; masked: string }[];
  doNow: string[];
  dont: string[];
  hotline: Hotline;
  evidence: {
    findings: string;
    sources: { title: string; uri: string }[];
    queries?: string[];
    webRisk: { domain: string; threats: string[] }[];
  };
  community: {
    repeatIndicators: { kind: string; masked: string; count: number; countries: Record<string, number> }[];
    similar: { id: string; distance: number; summary: string; scamType: string; country: string }[];
    campaign: { id: string; new: boolean; title: string; count: number } | null;
  };
  extractedText: string;
  shared: boolean;
  cached?: boolean;
  timingMs: number;
  model: { model?: string };
}

export interface StageEvent {
  id: "triage" | "evidence" | "intel" | "advice";
  status: "running" | "done" | "error";
  ms?: number;
}

export interface Signal {
  tactic: string;
  label: string;
  evidence: string;
  risk: number;
  t: number;
  by: "live" | "deep";
}

export interface Campaign {
  id: string;
  title: string;
  scamType: string;
  summary: string;
  count: number;
  countries: Record<string, number>;
  channels: Record<string, number>;
  tactics: string[];
  firstSeen: string;
  lastSeen: string;
  spark?: number[];
  last7?: number;
  prev7?: number;
}

export interface Bulletin {
  id: string;
  title: string;
  threat_level: "low" | "elevated" | "high" | "critical";
  executive_summary: string;
  campaigns: {
    name: string;
    scam_type: string;
    trend: string;
    what_is_happening: string;
    tactics: string[];
    countries: string[];
    bank_controls: string[];
  }[];
  mule_signals: string[];
  customer_advisory: Record<Lang, string>;
  createdAt?: string;
  basedOn?: { reports: number; campaigns: number };
}

export interface Overview {
  stats: {
    reports?: number;
    verdicts?: Record<string, number>;
    byType?: Record<string, number>;
    byCountry?: Record<string, number>;
    liveSessions?: number;
    liveWarnings?: number;
    lossAvertedMYR?: number;
  };
  series: { day: string; scam: number; suspicious: number }[];
  tactics: { id: string; label: string; count: number }[];
  campaigns: Campaign[];
  feed: FeedItem[];
  indicators: { kind: string; masked: string; count: number; countries: Record<string, number> }[];
  bulletin: Bulletin | null;
}

export interface FeedItem {
  id: string;
  createdAt: string;
  country: string;
  scamType: string;
  verdict: Verdict;
  riskScore: number;
  headline: string;
  source: string;
}
