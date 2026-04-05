"use client";

import { useCallback, useEffect, useState } from "react";

import { API_BASE, apiFetch } from "@/lib/api";

export type QuotaResponse = {
  plan: string;
  limite_portes: number | null;
  portes_actuales: number;
  porcentaje_uso: number;
  facturacion_actual: number;
};

export function useEmpresaQuota() {
  const [data, setData] = useState<QuotaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`${API_BASE}/empresa/quota`, {
        credentials: "include",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }
      const json = (await res.json()) as Partial<QuotaResponse>;
      setData({
        plan: typeof json.plan === "string" ? json.plan : "",
        limite_portes: json.limite_portes ?? null,
        portes_actuales: Number(json.portes_actuales ?? 0),
        porcentaje_uso: Number(json.porcentaje_uso ?? 0),
        facturacion_actual: Number(json.facturacion_actual ?? 0),
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { data, loading, error, refresh };
}
