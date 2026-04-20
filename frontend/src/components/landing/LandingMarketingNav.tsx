"use client";

import Link from "next/link";

import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { AbLogoMark } from "./AbLogoMark";

export function LandingMarketingNav() {
  const { catalog } = useOptionalLocaleCatalog();
  const n = catalog.nav;
  return (
    <header className="sticky top-0 z-50 border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <Link
          href="/"
          className="flex items-center gap-3 text-white"
          aria-label="AB Logistics OS — inicio"
        >
          <AbLogoMark className="h-9 w-9 shrink-0" />
          <span className="text-base font-semibold tracking-tight sm:text-lg">
            AB Logistics <span className="font-medium text-zinc-500">OS</span>
          </span>
        </Link>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <LocaleSwitcher />
          <Link
            href="/precios"
            className="rounded-full border border-transparent px-3 py-2 text-xs font-semibold uppercase tracking-widest text-zinc-400 transition hover:text-white"
          >
            {n.pricing}
          </Link>
          <Link
            href="/help"
            className="rounded-full border border-transparent px-3 py-2 text-xs font-semibold uppercase tracking-widest text-zinc-400 transition hover:text-white"
          >
            {n.help}
          </Link>
          <Link
            href="/login"
            className="rounded-full border border-zinc-700 bg-zinc-900/50 px-4 py-2 text-xs font-semibold uppercase tracking-widest text-zinc-300 transition hover:border-emerald-500/40 hover:text-white"
          >
            {n.appLogin}
          </Link>
        </div>
      </div>
    </header>
  );
}
