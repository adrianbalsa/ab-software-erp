"use client";

import { useCallback, useEffect, useState } from "react";

import { API_BASE, apiFetch } from "@/lib/api";

export type EmpresaQuota = {
  plan_type: string;
  limite_vehiculos: number | null;
  vehiculos_actuales: number;
};

export function useEmpresaQuota() {
  const [data, setData] = useState<EmpresaQuota | null>(null);
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
      const json = (await res.json()) as EmpresaQuota;
      setData(json);
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
