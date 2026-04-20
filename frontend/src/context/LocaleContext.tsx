"use client";

import {
  createContext,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { type AppLocale, catalogs, pickLocale } from "@/i18n/catalog";

const STORAGE_KEY = "abl-locale";

type LocaleContextValue = {
  locale: AppLocale;
  setLocale: (next: AppLocale) => void;
  catalog: (typeof catalogs)["es"];
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

function readStoredLocale(): AppLocale {
  if (typeof window === "undefined") return "es";
  try {
    return pickLocale(window.localStorage.getItem(STORAGE_KEY));
  } catch {
    return "es";
  }
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<AppLocale>(() => readStoredLocale());

  const setLocale = useCallback((next: AppLocale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  useLayoutEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = locale;
    }
  }, [locale]);

  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      setLocale,
      catalog: catalogs[locale],
    }),
    [locale, setLocale],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocaleCatalog() {
  const ctx = useContext(LocaleContext);
  if (!ctx) {
    throw new Error("useLocaleCatalog must be used within LocaleProvider");
  }
  return ctx;
}

/** Safe for components that may render outside LocaleProvider (falls back to Spanish). */
export function useOptionalLocaleCatalog(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  return (
    ctx ?? {
      locale: "es",
      setLocale: () => {},
      catalog: catalogs.es,
    }
  );
}
