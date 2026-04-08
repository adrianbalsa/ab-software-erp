"use client";

import { useCallback, useEffect, useState } from "react";
import { z } from "zod";

import { API_BASE, apiFetch } from "@/lib/api";
import { DashboardStatsSchema } from "@/lib/schemas";

export type DashboardStatsData = {
  km_estimados: number;
  bultos: number;
  portes_count: number;
  clientes_activos: number;
  facturacion_estimada: number;
};

const DashboardStatsResponseSchema = z.object({
  message: z.string().optional(),
  data: DashboardStatsSchema,
});

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
      const json = await apiFetch<z.infer<typeof DashboardStatsResponseSchema>>(
        `${API_BASE}/dashboard/stats`,
        undefined,
        DashboardStatsResponseSchema,
      );
      const stats = json.data;
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
