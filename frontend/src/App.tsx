import { Building2, Info, MessageSquareWarning, PhoneCall, Type } from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";
import { COUNTRIES, Logo, Spinner } from "./components/ui";
import { ensureUser } from "./lib/firebase";
import { LANG_LABELS } from "./lib/i18n";
import { usePrefs } from "./lib/prefs";
import type { Lang } from "./lib/types";
import CheckPage from "./pages/CheckPage";

const LivePage = lazy(() => import("./pages/LivePage"));
const IntelPage = lazy(() => import("./pages/IntelPage"));
const HowPage = lazy(() => import("./pages/HowPage"));

const ROUTES = ["check", "live", "intel", "how"] as const;
type Route = (typeof ROUTES)[number];

function useRoute(): [Route, (r: Route) => void] {
  const read = () => {
    const h = window.location.hash.replace("#", "") as Route;
    return ROUTES.includes(h) ? h : "check";
  };
  const [route, setRoute] = useState<Route>(read);
  useEffect(() => {
    const on = () => setRoute(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return [route, (r) => (window.location.hash = r)];
}

export default function App() {
  const { t, lang, setLang, country, setCountry, elder, setElder } = usePrefs();
  const [route, go] = useRoute();

  useEffect(() => {
    ensureUser().catch((e) => console.error("anonymous sign-in failed", e));
  }, []);

  const nav = [
    { id: "check" as const, label: t("navCheck"), icon: MessageSquareWarning },
    { id: "live" as const, label: t("navLive"), icon: PhoneCall },
    { id: "intel" as const, label: t("navIntel"), icon: Building2 },
    { id: "how" as const, label: t("navHow"), icon: Info },
  ];

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-brand-100 bg-white/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5">
          <a href="#check" className="flex items-center gap-2" aria-label="Kawal home">
            <Logo className="h-9 w-9" />
            <div className="leading-tight">
              <div className="text-lg font-extrabold tracking-tight text-brand-950">Kawal</div>
              <div className="hidden text-[11px] font-medium text-brand-700/80 sm:block">{t("tagline")}</div>
            </div>
          </a>

          <nav className="order-3 -mx-1 flex w-full gap-1 overflow-x-auto sm:order-none sm:mx-0 sm:w-auto sm:flex-1 sm:justify-center">
            {nav.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => go(id)}
                aria-current={route === id ? "page" : undefined}
                className={`flex shrink-0 items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-semibold transition ${
                  route === id ? "bg-brand-900 text-white shadow" : "text-brand-900/70 hover:bg-brand-50"
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <select
              aria-label={t("country")}
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className="rounded-lg border border-brand-100 bg-white px-2 py-1.5 text-sm font-medium"
            >
              {Object.entries(COUNTRIES).map(([cc, name]) => (
                <option key={cc} value={cc}>
                  {name}
                </option>
              ))}
            </select>
            <div className="flex rounded-lg border border-brand-100 p-0.5" role="group" aria-label="Language">
              {(Object.keys(LANG_LABELS) as Lang[]).map((l) => (
                <button
                  key={l}
                  onClick={() => setLang(l)}
                  aria-pressed={lang === l}
                  className={`rounded-md px-2 py-1 text-xs font-bold ${lang === l ? "bg-brand-100 text-brand-900" : "text-slate-500"}`}
                >
                  {LANG_LABELS[l]}
                </button>
              ))}
            </div>
            <button
              onClick={() => setElder(!elder)}
              aria-pressed={elder}
              title={t("elder")}
              className={`rounded-lg border p-1.5 ${elder ? "border-brand-600 bg-brand-600 text-white" : "border-brand-100 text-brand-800"}`}
            >
              <Type className="h-4 w-4" />
              <span className="sr-only">{t("elder")}</span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:py-10">
        <Suspense fallback={<div className="flex justify-center py-20 text-brand-700"><Spinner className="h-8 w-8" /></div>}>
          {route === "check" && <CheckPage />}
          {route === "live" && <LivePage />}
          {route === "intel" && <IntelPage />}
          {route === "how" && <HowPage />}
        </Suspense>
      </main>

      <footer className="border-t border-brand-100 py-6 text-center text-xs text-slate-500">
        Kawal · Team AwanPurple · Google Cloud AI Builder Cup 2026 · Built with Gemini, Cloud Run, Firestore &amp; Firebase
      </footer>
    </div>
  );
}
