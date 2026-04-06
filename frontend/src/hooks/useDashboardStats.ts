"use client";

import { useCallback, useEffect, useState } from "react";

import { API_BASE, apiFetch, parseApiError } from "@/lib/api";

export type DashboardStatsData = {
  km_estimados: number;
  bultos: number;
  portes_count: number;
  clientes_activos: number;
  facturacion_estimada: number;
};

/** Alineado con GET /dashboard/stats: `{ message, data }` (payload anidado). */
export type StatsResponse = {
  message: string;
  data: DashboardStatsData;
};

export function useDashboardStats(options?: { enabled?: boolean }) {
  const enabled = options?.enabled !== false;
  const [data, setData] = useState<DashboardStatsData | null>(null);
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
      const res = await apiFetch(`${API_BASE}/dashboard/stats`, {
        credentials: "include",
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res));
      }
      const json = (await res.json()) as Partial<StatsResponse>;
      const stats = (json?.data ?? {}) as Record<string, any>;
      setData({
        km_estimados: Number(stats.km_estimados ?? 0),
        bultos: Number(stats.bultos ?? 0),
        portes_count: Number(stats.portes_count ?? 0),
        clientes_activos: Number(stats.clientes_activos ?? 0),
        facturacion_estimada: Number(stats.facturacion_estimada ?? 0),
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
