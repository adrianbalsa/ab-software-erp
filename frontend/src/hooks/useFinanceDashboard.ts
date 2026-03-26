"use client";

import { useCallback, useEffect, useState } from "react";

import { API_BASE, authHeaders } from "@/lib/api";

export type FinanceMensualBar = {
  periodo: string;
  ingresos: number;
  gastos: number;
};

export type FinanceTesoreriaMensual = {
  periodo: string;
  ingresos_facturados: number;
  cobros_reales: number;
};

export type GastoBucketCinco = {
  name: string;
  value: number;
};

export type FinanceDashboard = {
  ingresos: number;
  gastos: number;
  ebitda: number;
  total_km_estimados_snapshot: number;
  margen_km_eur: number | null;
  ingresos_vs_gastos_mensual: FinanceMensualBar[];
  tesoreria_mensual: FinanceTesoreriaMensual[];
  gastos_por_bucket_cinco: GastoBucketCinco[];
  margen_neto_km_mes_actual: number | null;
  margen_neto_km_mes_anterior: number | null;
  variacion_margen_km_pct: number | null;
  km_facturados_mes_actual: number | null;
  km_facturados_mes_anterior: number | null;
};

export function useFinanceDashboard(options?: { enabled?: boolean }) {
  const enabled = options?.enabled !== false;
  const [data, setData] = useState<FinanceDashboard | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/finance/dashboard`, {
        credentials: "include",
        headers: { ...authHeaders() },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          typeof err?.detail === "string" ? err.detail : `HTTP ${res.status}`,
        );
      }
      const json = (await res.json()) as Partial<FinanceDashboard>;
      setData({
        ingresos: json.ingresos ?? 0,
        gastos: json.gastos ?? 0,
        ebitda: json.ebitda ?? 0,
        total_km_estimados_snapshot: json.total_km_estimados_snapshot ?? 0,
        margen_km_eur: json.margen_km_eur ?? null,
        ingresos_vs_gastos_mensual: json.ingresos_vs_gastos_mensual ?? [],
        tesoreria_mensual: json.tesoreria_mensual ?? [],
        gastos_por_bucket_cinco: json.gastos_por_bucket_cinco ?? [],
        margen_neto_km_mes_actual: json.margen_neto_km_mes_actual ?? null,
        margen_neto_km_mes_anterior: json.margen_neto_km_mes_anterior ?? null,
        variacion_margen_km_pct: json.variacion_margen_km_pct ?? null,
        km_facturados_mes_actual: json.km_facturados_mes_actual ?? null,
        km_facturados_mes_anterior: json.km_facturados_mes_anterior ?? null,
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      setError(null);
      setData(null);
      return;
    }
    void refresh();
  }, [enabled, refresh]);

  return { data, loading, error, refresh };
}
