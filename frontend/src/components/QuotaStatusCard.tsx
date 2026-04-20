"use client";

import Link from "next/link";
import { useState } from "react";

import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { useRole } from "@/hooks/useRole";
import { useEmpresaQuota } from "@/hooks/useEmpresaQuota";
import { createStripeBillingPortalUrl, isOwnerLike, type AppRbacRole } from "@/lib/api";

function canOpenStripePortal(role: AppRbacRole): boolean {
  return isOwnerLike(role) || role === "developer";
}

function normalizePlan(raw: string): "starter" | "pro" | "enterprise" {
  const s = (raw || "").trim().toLowerCase();
  if (s === "pro" || s === "professional") return "pro";
  if (s === "enterprise" || s === "ent" || s === "unlimited") return "enterprise";
  return "starter";
}

function barToneClasses(pct: number): string {
  if (pct >= 90) return "bg-rose-500 animate-pulse";
  if (pct >= 70) return "bg-amber-500";
  return "bg-emerald-500";
}

export function QuotaStatusCard() {
  const { catalog } = useOptionalLocaleCatalog();
  const q = catalog.quota;
  const { role } = useRole();
  const { data, loading, error } = useEmpresaQuota();
  const [portalBusy, setPortalBusy] = useState(false);
  const [portalErr, setPortalErr] = useState<string | null>(null);

  const showBillingPortal = canOpenStripePortal(role);

  async function openStripePortal() {
    setPortalErr(null);
    setPortalBusy(true);
    try {
      const url = await createStripeBillingPortalUrl();
      window.location.assign(url);
    } catch (e) {
      setPortalErr(e instanceof Error ? e.message : String(e));
    } finally {
      setPortalBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 px-3 py-3 animate-pulse">
        <div className="mb-3 h-3 w-24 rounded bg-zinc-800" />
        <div className="h-2 w-full rounded-full bg-zinc-800" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-[11px] text-zinc-500">
        {error ? `${q.quotaPrefix} ${error}` : q.noData}
      </div>
    );
  }

  const plan = normalizePlan(data.plan);
  const used = data.portes_actuales ?? 0;
  const limit = data.limite_portes;

  const pctFinite = limit != null && limit > 0 ? Math.min(100, (used / limit) * 100) : null;

  const barWidth = pctFinite != null ? pctFinite : 100;
  const barClasses = pctFinite != null ? barToneClasses(pctFinite) : "bg-emerald-500/90";

  let message: string;
  if (plan === "starter") {
    message = q.starterMsg.replace("{used}", String(used));
  } else if (plan === "pro") {
    message = q.proMsg;
  } else {
    message = q.enterpriseMsg.replace("{used}", String(used));
  }

  const upgradeHref =
    plan === "starter"
      ? "/payments/create-checkout?plan=pro"
      : plan === "pro"
        ? "/payments/create-checkout?plan=enterprise"
        : null;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 px-3 py-3 shadow-inner">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400">{q.fleetQuota}</span>
        {limit != null ? (
          <span className="text-[11px] tabular-nums text-zinc-400">
            {used}/{limit}
          </span>
        ) : (
          <span className="text-[11px] text-emerald-400/90">∞</span>
        )}
      </div>
      <div className="mb-3 h-2 w-full overflow-hidden rounded-full bg-zinc-900">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${barClasses}`}
          style={{ width: `${barWidth}%` }}
        />
      </div>
      <p className="mb-3 text-xs leading-snug text-zinc-400">{message}</p>
      {upgradeHref ? (
        <Link
          href={upgradeHref}
          className="block w-full rounded-lg border border-emerald-500/40 bg-emerald-600 py-2 text-center text-xs font-semibold text-zinc-950 transition-colors hover:bg-emerald-500"
        >
          {q.upgrade}
        </Link>
      ) : null}
      {showBillingPortal ? (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => void openStripePortal()}
            disabled={portalBusy}
            className="block w-full rounded-lg border border-zinc-600 bg-zinc-800/80 py-2 text-center text-xs font-semibold text-zinc-100 transition-colors hover:border-zinc-500 hover:bg-zinc-800 disabled:opacity-50"
          >
            {portalBusy ? q.manageSubscriptionBusy : q.manageSubscription}
          </button>
          {portalErr ? <p className="mt-1 text-center text-[10px] text-rose-400/90">{portalErr}</p> : null}
        </div>
      ) : null}
      <Link
        href="/help/billing"
        className="mt-2 block text-center text-[11px] font-medium text-emerald-500/90 underline-offset-2 hover:text-emerald-400 hover:underline"
      >
        {q.helpQuotaBilling}
      </Link>
    </div>
  );
}
