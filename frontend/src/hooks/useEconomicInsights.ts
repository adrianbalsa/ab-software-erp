"use client";

import { useCallback, useEffect, useState } from "react";

import { API_BASE, authHeaders, parseApiError } from "@/lib/api";

export type EconomicInsightsData = {
  coste_medio_km_ultimos_30d: number | null;
  km_operativos_ultimos_30d: number;
  gastos_operativos_ultimos_30d: number;
  top_clientes_rentabilidad: Array<{
    cliente_id: string;
    cliente_nombre: string;
    ingresos_netos_eur: number;
    margen_pct: number;
    gasto_asignado_eur: number;
  }>;
  ingresos_vs_gastos_mensual: Array<{ periodo: string; ingresos: number; gastos: number }>;
  margen_km_vs_gasoil_mensual: Array<{
    periodo: string;
    margen_neto_km_eur: number | null;
    coste_combustible_por_km_eur: number | null;
  }>;
  gastos_por_categoria: Array<{ name: string; value: number }>;
  punto_equilibrio_mensual: {
    periodo_referencia: string;
    gastos_fijos_mes_eur: number;
    gastos_variables_mes_eur: number;
    ingresos_mes_eur: number;
    margen_contribucion_ratio: number | null;
    ingreso_equilibrio_estimado_eur: number | null;
    km_equilibrio_estimados: number | null;
    nota_metodologia: string;
  };
};

export function useEconomicInsights(options: { enabled: boolean }) {
  const { enabled } = options;
  const [data, setData] = useState<EconomicInsightsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/dashboard/economic-insights`, {
        credentials: "include",
        headers: { ...authHeaders(), Accept: "application/json" },
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res));
      }
      const json = (await res.json()) as EconomicInsightsData;
      setData(json);
    } catch (e: unknown) {
      setData(null);
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (enabled) void refresh();
  }, [enabled, refresh]);

  return { data, loading, error, refresh };
}
