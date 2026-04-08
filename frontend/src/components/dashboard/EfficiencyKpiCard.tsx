"use client";
import { Route } from "lucide-react";

function formatEURPerKm(n: number | null) {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n.toLocaleString("es-ES", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  })} €/km`;
}

export type EfficiencyKpiCardProps = {
  margenNetoKm: number | null;
  margenNetoKmMesAnterior: number | null;
  variacionPct: number | null;
  /** Km facturados (snapshot) en el mes — validación del denominador del margen/km */
  kmFacturadosMes?: number | null;
  kmFacturadosMesAnterior?: number | null;
  loading?: boolean;
};

function formatKm(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n.toLocaleString("es-ES", { maximumFractionDigits: 1 })} km`;
}

export function EfficiencyKpiCard({
  margenNetoKm,
  margenNetoKmMesAnterior,
  variacionPct,
  kmFacturadosMes,
  kmFacturadosMesAnterior,
  loading,
}: EfficiencyKpiCardProps) {
  if (loading) {
    return (
      <div className="dashboard-bento animate-pulse rounded-2xl p-6">
        <div className="mb-3 h-4 w-1/3 rounded bg-zinc-800" />
        <div className="mb-2 h-10 w-2/3 rounded bg-zinc-800/80" />
        <div className="h-3 w-1/2 rounded bg-zinc-800/60" />
      </div>
    );
  }

  const positive = variacionPct != null && variacionPct >= 0;
  const showMom =
    variacionPct != null && !Number.isNaN(variacionPct) && Number.isFinite(variacionPct);

  return (
    <div className="dashboard-bento rounded-2xl p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="mb-1 text-sm font-medium text-zinc-400">Margen neto por km</p>
          <p className="mb-2 text-xs text-zinc-500">
            (Ingresos − Gastos) ÷ km facturados en el mes · mismo criterio que el Math Engine (sin IVA)
          </p>
          <h3 className="text-3xl font-bold tracking-tight text-zinc-100">{formatEURPerKm(margenNetoKm)}</h3>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            {showMom ? (
              <span
                className={
                  positive
                    ? "inline-flex items-center gap-1 font-semibold text-emerald-400"
                    : "inline-flex items-center gap-1 font-semibold text-zinc-400"
                }
              >
                <span aria-hidden>{positive ? "↑" : "↓"}</span>
                {positive ? "+" : "−"}
                {Math.abs(variacionPct).toFixed(1)}% vs mes anterior
              </span>
            ) : (
              <span className="text-zinc-500">Sin comparativa (sin km o sin mes previo comparable)</span>
            )}
          </div>
          <p className="mt-3 text-xs text-zinc-500">
            Km facturados (mes):{" "}
            <span className="font-semibold text-zinc-200">{formatKm(kmFacturadosMes)}</span>
            {kmFacturadosMesAnterior != null && kmFacturadosMesAnterior > 0 && (
              <>
                {" "}
                · mes ant.:{" "}
                <span className="font-medium text-zinc-400">{formatKm(kmFacturadosMesAnterior)}</span>
              </>
            )}
          </p>
          {margenNetoKmMesAnterior != null && (
            <p className="mt-2 text-xs text-zinc-500">
              Margen/km mes anterior:{" "}
              <span className="font-medium text-zinc-300">{formatEURPerKm(margenNetoKmMesAnterior)}</span>
            </p>
          )}
        </div>
        <div className="shrink-0 rounded-xl bg-emerald-500/15 p-3 text-emerald-400">
          <Route className="h-7 w-7" aria-hidden />
        </div>
      </div>
    </div>
  );
}
