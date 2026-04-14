"use client";

import Link from "next/link";

import { useEmpresaQuota } from "@/hooks/useEmpresaQuota";

function normalizePlan(raw: string): "starter" | "pro" | "enterprise" {
  const s = (raw || "").trim().toLowerCase();
  if (s === "pro" || s === "professional") return "pro";
  if (s === "enterprise" || s === "ent" || s === "unlimited")
    return "enterprise";
  return "starter";
}

function barToneClasses(pct: number): string {
  if (pct >= 90) return "bg-rose-500 animate-pulse";
  if (pct >= 70) return "bg-amber-500";
  return "bg-emerald-500";
}

export function QuotaStatusCard() {
  const { data, loading, error } = useEmpresaQuota();

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
        {error ? `Cuota: ${error}` : "Sin datos de cuota"}
      </div>
    );
  }

  const plan = normalizePlan(data.plan);
  const used = data.portes_actuales ?? 0;
  const limit = data.limite_portes;

  const pctFinite =
    limit != null && limit > 0
      ? Math.min(100, (used / limit) * 100)
      : null;

  const barWidth = pctFinite != null ? pctFinite : 100;
  const barClasses =
    pctFinite != null
      ? barToneClasses(pctFinite)
      : "bg-emerald-500/90";

  let message: string;
  if (plan === "starter") {
    message = `Estás usando ${used} de 5 vehículos. Pásate a PRO para gestionar hasta 25.`;
  } else if (plan === "pro") {
    message =
      "Módulo ESG bloqueado. Sube a ENTERPRISE para certificar tu huella de carbono.";
  } else {
    message = `Plan Enterprise · ${used} vehículo${used === 1 ? "" : "s"} registrados (sin límite).`;
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
        <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
          Cuota flota
        </span>
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
          Mejorar Plan
        </Link>
      ) : null}
    </div>
  );
}
