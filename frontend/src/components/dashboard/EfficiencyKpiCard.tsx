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
      <div className="ab-card p-6 rounded-2xl animate-pulse">
        <div className="h-4 bg-zinc-200/90 rounded w-1/3 mb-3" />
        <div className="h-10 bg-zinc-100 rounded w-2/3 mb-2" />
        <div className="h-3 bg-zinc-100 rounded w-1/2" />
      </div>
    );
  }

  const positive = variacionPct != null && variacionPct >= 0;
  const showMom =
    variacionPct != null && !Number.isNaN(variacionPct) && Number.isFinite(variacionPct);

  return (
    <div className="ab-card p-6 rounded-2xl border-emerald-200/60 bg-gradient-to-br from-white to-emerald-50/40">
      <div className="flex justify-between items-start gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-zinc-500 mb-1">
            Margen neto por km
          </p>
          <p className="text-xs text-zinc-500 mb-2">
            (Ingresos − Gastos) ÷ km facturados en el mes · mismo criterio que el Math
            Engine (sin IVA)
          </p>
          <h3 className="text-3xl font-bold text-zinc-800 tracking-tight">
            {formatEURPerKm(margenNetoKm)}
          </h3>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            {showMom ? (
              <span
                className={
                  positive
                    ? "inline-flex items-center gap-1 font-semibold text-emerald-600"
                    : "inline-flex items-center gap-1 font-semibold text-zinc-600"
                }
              >
                <span aria-hidden>{positive ? "↑" : "↓"}</span>
                {positive ? "+" : "−"}
                {Math.abs(variacionPct).toFixed(1)}% vs mes anterior
              </span>
            ) : (
              <span className="text-zinc-500">
                Sin comparativa (sin km o sin mes previo comparable)
              </span>
            )}
          </div>
          <p className="text-xs text-zinc-600 mt-3">
            Km facturados (mes):{" "}
            <span className="font-semibold text-zinc-800">
              {formatKm(kmFacturadosMes)}
            </span>
            {kmFacturadosMesAnterior != null && kmFacturadosMesAnterior > 0 && (
              <>
                {" "}
                · mes ant.:{" "}
                <span className="font-medium text-zinc-700">
                  {formatKm(kmFacturadosMesAnterior)}
                </span>
              </>
            )}
          </p>
          {margenNetoKmMesAnterior != null && (
            <p className="text-xs text-zinc-500 mt-2">
              Margen/km mes anterior:{" "}
              <span className="font-medium text-zinc-700">
                {formatEURPerKm(margenNetoKmMesAnterior)}
              </span>
            </p>
          )}
        </div>
        <div className="p-3 bg-emerald-100/90 rounded-xl text-emerald-700 shrink-0">
          <Route className="w-7 h-7" aria-hidden />
        </div>
      </div>
    </div>
  );
}
