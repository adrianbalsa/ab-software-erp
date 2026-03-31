"use client";

import { useCallback, useEffect, useState } from "react";

import { API_BASE, apiFetch, authHeaders } from "@/lib/api";

export type EcoDashboard = {
  anio: number;
  mes: number;
  co2_kg_portes_facturados: number;
  num_portes_facturados: number;
  scope_1_kg: number;
  scope_3_kg: number;
  co2_per_ton_km: number;
};

export function useEcoDashboard(options?: { enabled?: boolean }) {
  const enabled = options?.enabled !== false;
  const [data, setData] = useState<EcoDashboard | null>(null);
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
      const res = await apiFetch(`${API_BASE}/eco/dashboard/`, {
        credentials: "include",
        headers: { ...authHeaders() },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          typeof err?.detail === "string" ? err.detail : `HTTP ${res.status}`,
        );
      }
      const json = (await res.json()) as Partial<EcoDashboard>;
      setData({
        anio: json.anio ?? new Date().getFullYear(),
        mes: json.mes ?? new Date().getMonth() + 1,
        co2_kg_portes_facturados: json.co2_kg_portes_facturados ?? 0,
        num_portes_facturados: json.num_portes_facturados ?? 0,
        scope_1_kg: json.scope_1_kg ?? 0,
        scope_3_kg: json.scope_3_kg ?? 0,
        co2_per_ton_km: json.co2_per_ton_km ?? 0,
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

