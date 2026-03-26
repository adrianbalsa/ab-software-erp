"use client";

import { useCallback, useEffect, useState } from "react";

import { API_BASE, authHeaders } from "@/lib/api";
import type { UUID } from "@/types";

export type FleetAlert = {
  tipo: "itv_vencimiento" | "seguro_vencimiento" | "proxima_revision_km";
  vehiculo_id: UUID;
  matricula: string | null;
  vehiculo: string | null;
  prioridad: "alta" | "media" | "baja";
  detalle: string;
  fecha_referencia: string | null;
  km_restantes: number | null;
};

export function useFleetAlerts(options?: { enabled?: boolean }) {
  const enabled = options?.enabled !== false;
  const [alerts, setAlerts] = useState<FleetAlert[]>([]);
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
      const res = await fetch(`${API_BASE}/flota/alerts`, {
        credentials: "include",
        headers: { ...authHeaders() },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          typeof err?.detail === "string" ? err.detail : `HTTP ${res.status}`,
        );
      }
      const json = (await res.json()) as FleetAlert[];
      setAlerts(json);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      setError(null);
      setAlerts([]);
      return;
    }
    void refresh();
  }, [enabled, refresh]);

  return { alerts, loading, error, refresh };
}
