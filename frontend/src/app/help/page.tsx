"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowRight, Search } from "lucide-react";

import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { HELP_ARTICLES, helpArticleSearchText, type HelpCategory } from "@/help/articles";
import { AbLogoMark } from "@/components/landing/AbLogoMark";

const CATEGORY_ORDER: HelpCategory[] = [
  "onboarding",
  "billing",
  "security",
  "compliance",
  "integrations",
  "support",
];

export default function HelpHubPage() {
  const { catalog, locale } = useOptionalLocaleCatalog();
  const h = catalog.helpHub;
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<HelpCategory | "all">("all");

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return HELP_ARTICLES.filter((a) => {
      if (cat !== "all" && a.category !== cat) return false;
      if (!needle) return true;
      return helpArticleSearchText(a, locale).includes(needle);
    });
  }, [q, cat, locale]);

  return (
    <div className="min-h-screen text-zinc-300">
      <header className="border-b border-zinc-800/80 bg-zinc-950/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <Link href="/" className="flex items-center gap-3 text-white">
            <AbLogoMark className="h-9 w-9 shrink-0" />
            <span className="text-base font-semibold tracking-tight">AB Logistics OS</span>
          </Link>
          <LocaleSwitcher />
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">{h.hubTitle}</h1>
        <p className="mt-4 max-w-3xl text-lg text-zinc-400">{h.hubSubtitle}</p>

        <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center">
          <label className="relative flex-1">
            <span className="sr-only">{h.searchLabel}</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={h.searchPlaceholder}
              className="w-full rounded-xl border border-zinc-800 bg-zinc-900/60 py-3 pl-10 pr-4 text-sm text-zinc-100 outline-none ring-emerald-500/30 placeholder:text-zinc-500 focus:border-emerald-500/40 focus:ring-2"
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setCat("all")}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition ${
              cat === "all"
                ? "bg-emerald-600 text-zinc-950"
                : "border border-zinc-700 bg-zinc-900/50 text-zinc-400 hover:border-zinc-600"
            }`}
          >
            {h.allCategories}
          </button>
          {CATEGORY_ORDER.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setCat(c)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition ${
                cat === c
                  ? "bg-emerald-600 text-zinc-950"
                  : "border border-zinc-700 bg-zinc-900/50 text-zinc-400 hover:border-zinc-600"
              }`}
            >
              {h.categories[c]}
            </button>
          ))}
        </div>

        {filtered.length === 0 ? (
          <p className="mt-10 text-center text-sm text-zinc-500">{h.noResults}</p>
        ) : (
          <ul className="mt-10 grid gap-4 sm:grid-cols-2">
            {filtered.map((a) => (
              <li key={a.slug}>
                <Link
                  href={`/help/${a.slug}`}
                  title={`${h.readArticle}: ${locale === "en" ? a.titles.en : a.titles.es}`}
                  className="group flex h-full flex-col rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 transition hover:border-emerald-500/30"
                >
                  <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-500/90">
                    {h.categories[a.category]}
                  </p>
                  <p className="mt-2 text-lg font-semibold text-white">
                    {locale === "en" ? a.titles.en : a.titles.es}
                  </p>
                  <p className="mt-2 flex-1 text-sm text-zinc-500">
                    {locale === "en" ? a.excerpts.en : a.excerpts.es}
                  </p>
                  <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-emerald-400">
                    {h.readArticle}
                    <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}

        <footer className="mt-16 border-t border-zinc-800/80 pt-8 text-center text-xs text-zinc-500">
          <p className="max-w-2xl mx-auto leading-relaxed">{h.footerLegal}</p>
          <p className="mt-4 flex flex-wrap justify-center gap-x-4 gap-y-2">
            <Link href="/precios" className="text-emerald-500/90 hover:text-emerald-400">
              {h.footerPricing}
            </Link>
            <Link href="/login" className="text-emerald-500/90 hover:text-emerald-400">
              {h.footerLogin}
            </Link>
          </p>
        </footer>
      </main>
    </div>
  );
}
