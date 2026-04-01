"use client";

import { useCallback, useEffect, useState } from "react";

import { API_BASE, apiFetch, parseApiError } from "@/lib/api";

export type DashboardStats = {
  ebitda_estimado: number;
  pendientes_cobro: number;
  km_totales_mes: number;
  bultos_mes: number;
};

export function useDashboardStats(options?: { enabled?: boolean }) {
  const enabled = options?.enabled !== false;
  const [data, setData] = useState<DashboardStats | null>(null);
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
      const json = (await res.json()) as DashboardStats;
      setData(json);
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
