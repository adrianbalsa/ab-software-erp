"use client";

import Link from "next/link";
import { PricingPlansCheckout } from "@/components/landing/PricingPlansCheckout";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";

export function PricingCheckout() {
  const { catalog } = useOptionalLocaleCatalog();
  const lp = catalog.landing.pricingPage;

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-700 dark:text-zinc-300">
      <header className="border-b border-zinc-200/90 dark:border-zinc-800/80 bg-zinc-50 dark:bg-zinc-950/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <Link href="/" className="text-sm font-semibold text-white hover:text-emerald-300 transition">
            AB Logistics OS
          </Link>
          <Link
            href="/login"
            className="inline-flex min-h-10 items-center rounded-full border border-zinc-700 px-4 py-2 text-xs font-semibold uppercase tracking-widest text-zinc-700 dark:text-zinc-300 hover:border-emerald-500/40 hover:text-white transition"
          >
            {lp.headerLogin}
          </Link>
        </div>
      </header>
      <main>
        <PricingPlansCheckout variant="full-page" />
      </main>
    </div>
  );
}
