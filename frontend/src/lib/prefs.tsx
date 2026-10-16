import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { DICTS, type TKey } from "./i18n";
import type { Lang } from "./types";

interface Prefs {
  lang: Lang;
  setLang: (l: Lang) => void;
  country: string;
  setCountry: (c: string) => void;
  elder: boolean;
  setElder: (v: boolean) => void;
  t: (key: TKey, vars?: Record<string, string | number>) => string;
}

const Ctx = createContext<Prefs | null>(null);

function stored<T extends string>(key: string, fallback: T): T {
  try {
    return (localStorage.getItem(key) as T) || fallback;
  } catch {
    return fallback;
  }
}

function save(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode */
  }
}

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => stored<Lang>("kawal.lang", "en"));
  const [country, setCountryState] = useState<string>(() => stored<string>("kawal.country", "MY"));
  const [elder, setElderState] = useState(() => stored<string>("kawal.elder", "0") === "1");

  useEffect(() => {
    document.documentElement.lang = lang === "zh" ? "zh-Hans" : lang;
    document.documentElement.classList.toggle("elder", elder);
  }, [lang, elder]);

  const value = useMemo<Prefs>(
    () => ({
      lang,
      country,
      elder,
      setLang: (l) => (setLangState(l), save("kawal.lang", l)),
      setCountry: (c) => (setCountryState(c), save("kawal.country", c)),
      setElder: (v) => (setElderState(v), save("kawal.elder", v ? "1" : "0")),
      t: (key, vars) => {
        let s: string = DICTS[lang][key] ?? DICTS.en[key];
        for (const [k, v] of Object.entries(vars ?? {})) s = s.replace(`{${k}}`, String(v));
        return s;
      },
    }),
    [lang, country, elder],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function usePrefs(): Prefs {
  const v = useContext(Ctx);
  if (!v) throw new Error("usePrefs outside PrefsProvider");
  return v;
}
