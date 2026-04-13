"use client";

import Link from "next/link";
import { AbLogoMark } from "./AbLogoMark";

export function LandingMarketingNav() {
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
        <Link
          href="/login"
          className="rounded-full border border-zinc-700 bg-zinc-900/50 px-4 py-2 text-xs font-semibold uppercase tracking-widest text-zinc-300 transition hover:border-emerald-500/40 hover:text-white"
        >
          Acceso Clientes
        </Link>
      </div>
    </header>
  );
}
