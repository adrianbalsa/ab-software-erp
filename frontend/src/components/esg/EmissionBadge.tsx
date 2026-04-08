"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { API_BASE, apiFetch, parseApiError } from "@/lib/api";

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
      const res = await apiFetch(`${API_BASE}/api/v1/esg/reporte-anual?year=${y}`, {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
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

  useEffect(() => {
    if (!error) return;
    toast.error(error, { id: "emission-badge-error" });
  }, [error]);

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
      <div className="dashboard-bento animate-pulse rounded-2xl border border-zinc-800/50 p-6">
        <div className="mb-3 h-4 w-1/2 rounded bg-zinc-800" />
        <div className="mb-2 h-10 w-2/3 rounded bg-zinc-800/80" />
        <div className="h-3 w-1/3 rounded bg-zinc-800/60" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="dashboard-bento rounded-2xl border border-zinc-800/50 p-6">
        <p className="text-sm font-medium text-zinc-300">Ahorro verde (CO₂)</p>
        <p className="mt-1 text-xs text-zinc-500">Datos no disponibles. Revisa el aviso en pantalla.</p>
      </div>
    );
  }

  const ahorroFmt = computed.ahorroKg.toLocaleString("es-ES", {
    maximumFractionDigits: 0,
  });
  const pctFmt = computed.pct.toLocaleString("es-ES", { maximumFractionDigits: 1 });

  return (
    <div
      className={`dashboard-bento rounded-2xl border p-6 ${
        computed.positive ? "border-emerald-500/30" : "border-zinc-800/50"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-zinc-400">Ahorro verde (CO₂)</p>
          <h3 className="text-3xl font-bold tracking-tight text-zinc-100">
            {ahorroFmt} <span className="text-sm font-semibold text-zinc-500">kg</span>
          </h3>
          <p className="mt-1 text-xs text-zinc-500">
            {computed.baselineKg > 0
              ? `${pctFmt}% vs baseline (sin bonus Euro VI)`
              : "Sin baseline disponible para el año actual"}
          </p>
        </div>
        <div
          className={`shrink-0 rounded-xl p-3 ${
            computed.positive ? "bg-emerald-500/15 text-emerald-400" : "bg-zinc-800 text-zinc-400"
          }`}
          aria-hidden
        >
          <span className="font-bold">CO₂</span>
        </div>
      </div>
    </div>
  );
}

