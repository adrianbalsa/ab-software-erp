"use client";

import { useEffect, useMemo, useState } from "react";

import { API_BASE, authHeaders, parseApiError } from "@/lib/api";

type Monthly = {
  mes: string;
  litros_consumidos: number;
  co2_emitido_kg: number;
  co2_baseline_kg: number;
  co2_ahorro_kg: number;
};

type AnnualResponse = {
  year: number;
  empresa_id: string;
  total_litros_consumidos: number;
  total_co2_emitido_kg: number;
  total_co2_baseline_kg: number;
  total_co2_ahorro_kg: number;
  meses: Monthly[];
};

export function EmissionBadge({ year }: { year?: number }) {
  const y = year ?? new Date().getFullYear();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AnnualResponse | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/esg/reporte-anual?year=${y}`, {
        method: "GET",
        credentials: "include",
        headers: { ...authHeaders(), Accept: "application/json" },
      });
      if (!res.ok) throw new Error(await parseApiError(res));
      setData((await res.json()) as AnnualResponse);
    } catch (e: unknown) {
      setData(null);
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    const t = window.setInterval(() => void refresh(), 60_000);
    return () => window.clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [y]);

  const computed = useMemo(() => {
    const ahorroKg = data?.total_co2_ahorro_kg ?? 0;
    const baselineKg = data?.total_co2_baseline_kg ?? 0;
    const pct = baselineKg > 0 ? (ahorroKg / baselineKg) * 100 : 0;
    return {
      ahorroKg,
      baselineKg,
      pct,
      positive: ahorroKg > 0,
    };
  }, [data]);

  if (loading) {
    return (
      <div className="ab-card p-6 rounded-2xl animate-pulse border border-slate-100/80">
        <div className="h-4 bg-slate-200/90 rounded w-1/2 mb-3" />
        <div className="h-10 bg-slate-200/70 rounded w-2/3 mb-2" />
        <div className="h-3 bg-slate-200/70 rounded w-1/3" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="ab-card p-6 rounded-2xl border border-amber-200/80 bg-amber-50/60">
        <p className="text-sm font-medium text-amber-900">Ahorro verde</p>
        <p className="text-xs text-amber-900/80 mt-1">{error ?? "Sin datos"}</p>
      </div>
    );
  }

  const ahorroFmt = computed.ahorroKg.toLocaleString("es-ES", {
    maximumFractionDigits: 0,
  });
  const pctFmt = computed.pct.toLocaleString("es-ES", { maximumFractionDigits: 1 });

  return (
    <div
      className={`ab-card p-6 rounded-2xl border ${
        computed.positive ? "border-emerald-200/70 bg-emerald-50/35" : "border-slate-200/80 bg-slate-50/30"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-slate-600">Ahorro verde (CO₂)</p>
          <h3 className="text-3xl font-bold text-slate-800 tracking-tight">
            {ahorroFmt} <span className="text-sm font-semibold text-slate-600">kg</span>
          </h3>
          <p className="text-xs text-slate-600 mt-1">
            {computed.baselineKg > 0
              ? `${pctFmt}% vs baseline (sin bonus Euro VI)`
              : "Sin baseline disponible para el año actual"}
          </p>
        </div>
        <div
          className={`p-3 rounded-xl shrink-0 ${
            computed.positive ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"
          }`}
          aria-hidden
        >
          <span className="font-bold">CO₂</span>
        </div>
      </div>
    </div>
  );
}

