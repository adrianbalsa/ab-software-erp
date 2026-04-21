"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle2, Sparkles } from "lucide-react";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";

export function LandingHero() {
  const { catalog } = useOptionalLocaleCatalog();
  const l = catalog.landing.heroLegacy;

  return (
    <div className="relative overflow-hidden px-4 pt-16 pb-20 sm:pt-24 sm:pb-28">
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(59, 130, 246, 0.35), transparent), radial-gradient(ellipse 60% 40% at 100% 0%, rgba(16, 185, 129, 0.15), transparent)",
        }}
      />
      <div className="relative mx-auto max-w-4xl text-center">
        <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-zinc-700/80 bg-zinc-900/60 px-3 py-1 text-xs font-medium text-emerald-400/90 sm:text-sm">
          <Sparkles className="h-3.5 w-3.5 shrink-0" />
          {l.pill}
        </p>
        <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-5xl sm:leading-[1.1]">
          {l.titlePrefix}{" "}
          <span className="bg-gradient-to-r from-blue-400 via-sky-400 to-emerald-400 bg-clip-text text-transparent">
            {l.titleHighlight}
          </span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-zinc-300 sm:text-lg">
          {l.description}
        </p>
        <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <a
            href="#roi-simulator"
            className="inline-flex w-full sm:w-auto items-center justify-center gap-2 rounded-full bg-blue-500 px-8 py-3.5 text-base font-semibold text-white shadow-xl shadow-blue-500/30 transition hover:bg-blue-400"
          >
            {l.primaryCta}
            <ArrowRight className="h-4 w-4" />
          </a>
          <Link
            href="/login"
            className="inline-flex w-full sm:w-auto items-center justify-center rounded-full border border-zinc-600 bg-zinc-900/50 px-8 py-3.5 text-base font-semibold text-zinc-200 transition hover:border-zinc-500 hover:bg-zinc-800"
          >
            {l.secondaryCta}
          </Link>
        </div>
        <ul className="mt-5 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-zinc-300 sm:text-sm">
          {l.trustSignals.map((signal) => (
            <li key={signal} className="inline-flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
              <span>{signal}</span>
            </li>
          ))}
        </ul>
        <p className="mt-10 text-xs sm:text-sm text-zinc-300 max-w-xl mx-auto leading-relaxed border border-zinc-800/80 rounded-lg px-4 py-2.5 bg-zinc-900/40">
          {l.complianceNote}
        </p>
      </div>
    </div>
  );
}
