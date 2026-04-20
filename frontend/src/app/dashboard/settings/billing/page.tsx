"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { useLocaleCatalog } from "@/context/LocaleContext";
import { useEmpresaQuota } from "@/hooks/useEmpresaQuota";
import { createStripeBillingPortalUrl } from "@/lib/api";
import { BadgeEuro, ExternalLink } from "lucide-react";

function normalizePlan(raw: string): "starter" | "pro" | "enterprise" {
  const s = (raw || "").trim().toLowerCase();
  if (s === "pro" || s === "professional") return "pro";
  if (s === "enterprise" || s === "ent" || s === "unlimited") return "enterprise";
  return "starter";
}

export default function BillingSettingsPage() {
  const { catalog } = useLocaleCatalog();
  const b = catalog.billingPage;
  const { data, loading, error, refresh } = useEmpresaQuota();
  const [portalLoading, setPortalLoading] = useState(false);
  const [portalError, setPortalError] = useState<string | null>(null);

  const openPortal = useCallback(async () => {
    setPortalError(null);
    setPortalLoading(true);
    try {
      const url = await createStripeBillingPortalUrl();
      window.location.href = url;
    } catch (e) {
      setPortalError(e instanceof Error ? e.message : b.errorPrefix);
    } finally {
      setPortalLoading(false);
    }
  }, [b.errorPrefix]);

  const plan = data ? normalizePlan(data.plan) : "starter";
  const used = data?.portes_actuales ?? 0;
  const limit = data?.limite_portes;

  return (
    <AppShell active="billing">
      <main className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-zinc-950">
        <header className="z-10 flex min-h-16 shrink-0 flex-wrap items-center justify-between gap-4 border-b border-zinc-800 bg-zinc-950/90 px-6 py-4 backdrop-blur-md">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">{b.title}</h1>
            <p className="mt-0.5 text-sm text-zinc-400">{b.subtitle}</p>
          </div>
          <LocaleSwitcher />
        </header>

        <div className="max-w-2xl space-y-8 p-6 sm:p-8">
          <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
            <div className="flex items-center gap-2 text-zinc-200">
              <BadgeEuro className="h-5 w-5 text-emerald-500" aria-hidden />
              <h2 className="text-lg font-semibold">{b.planLabel}</h2>
            </div>
            {loading ? (
              <p className="mt-4 text-sm text-zinc-500">…</p>
            ) : error ? (
              <p className="mt-4 text-sm text-rose-400">{error}</p>
            ) : (
              <p className="mt-4 text-sm capitalize text-zinc-300">{plan}</p>
            )}
            <p className="mt-2 text-xs text-zinc-500">
              {b.usageLabel}:{" "}
              <span className="font-medium text-zinc-300">
                {used}
                {limit != null ? ` / ${limit}` : " / ∞"}
              </span>
            </p>
            <button
              type="button"
              onClick={() => refresh()}
              className="mt-4 text-xs font-medium text-emerald-500/90 hover:text-emerald-400"
            >
              {b.refresh}
            </button>
          </section>

          <section className="space-y-3">
            <button
              type="button"
              disabled={portalLoading}
              onClick={() => void openPortal()}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-emerald-500 disabled:opacity-60"
            >
              {portalLoading ? b.loadingPortal : b.portalCta}
              <ExternalLink className="h-4 w-4 opacity-80" aria-hidden />
            </button>
            {portalError ? (
              <p className="text-sm text-rose-400">
                {b.errorPrefix}: {portalError}
              </p>
            ) : (
              <p className="text-xs text-zinc-500">{b.portalHint}</p>
            )}
            <p className="text-xs text-zinc-600">{b.portalDisabled}</p>
          </section>

          <section className="flex flex-col gap-2 sm:flex-row">
            {plan === "starter" ? (
              <Link
                href="/payments/create-checkout?plan=pro"
                className="rounded-xl border border-emerald-500/40 bg-emerald-950/30 px-4 py-3 text-center text-sm font-semibold text-emerald-200 transition hover:bg-emerald-900/40"
              >
                {b.upgradePro}
              </Link>
            ) : null}
            {plan !== "enterprise" ? (
              <Link
                href="/payments/create-checkout?plan=enterprise"
                className="rounded-xl border border-zinc-700 bg-zinc-900/50 px-4 py-3 text-center text-sm font-semibold text-zinc-200 transition hover:border-zinc-600"
              >
                {b.upgradeEnt}
              </Link>
            ) : null}
          </section>

          <p className="text-center text-xs text-zinc-600">
            <Link href="/help/billing" className="text-emerald-500/90 hover:text-emerald-400">
              {catalog.helpIndex.billingCard}
            </Link>
            {" · "}
            <Link href="/precios" className="text-emerald-500/90 hover:text-emerald-400">
              {catalog.nav.pricing}
            </Link>
          </p>
        </div>
      </main>
    </AppShell>
  );
}
