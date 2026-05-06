"use client";

import { useCallback, useEffect, useState } from "react";

import { API_BASE, apiFetch } from "@/lib/api";
import { isLikelyNetworkFetchError, userFacingFetchFailureMessage } from "@/lib/api-base";

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    globalThis.setTimeout(resolve, ms);
  });
}

export type QuotaResponse = {
  plan: string;
  limite_portes: number | null;
  portes_actuales: number;
  porcentaje_uso: number;
  facturacion_actual: number;
  /** Plazas de panel (owner + gestores); `null` = Enterprise ilimitado. */
  limite_usuarios_equipo: number | null;
  usuarios_equipo_actuales: number;
  /** Solo Compliance: tope de facturas selladas por mes natural; `null` en planes superiores. */
  limite_facturas_mes: number | null;
  facturas_emitidas_mes_actual: number;
  must_complete_checkout?: boolean;
  billing_suspended?: boolean;
};

export function useEmpresaQuota() {
  const [data, setData] = useState<QuotaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      for (let attempt = 0; attempt < 2; attempt++) {
        try {
          if (attempt > 0) await delay(400);
          const res = await apiFetch(`${API_BASE}/empresa/quota`, {
            credentials: "include",
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(
              typeof (err as { detail?: unknown }).detail === "string"
                ? String((err as { detail: string }).detail)
                : `HTTP ${res.status}`,
            );
          }
          const json = (await res.json()) as Record<string, unknown>;
          const planRaw = (json.plan_type ?? json.plan) as string | undefined;
          const limiteFlota = (json.limite_vehiculos ?? json.limite_portes) as number | null | undefined;
          const usadosFlota = (json.vehiculos_actuales ?? json.portes_actuales) as number | string | undefined;
          const limiteTeam = json.limite_usuarios_equipo as number | null | undefined;
          const usadosTeam = json.usuarios_equipo_actuales as number | string | undefined;
          const limiteInv = json.limite_facturas_mes as number | null | undefined;
          const usadosInv = json.facturas_emitidas_mes_actual as number | string | undefined;
          setData({
            plan: typeof planRaw === "string" ? planRaw : "",
            limite_portes: limiteFlota == null ? null : Number(limiteFlota),
            portes_actuales: Number(usadosFlota ?? 0),
            porcentaje_uso: Number(json.porcentaje_uso ?? 0),
            facturacion_actual: Number(json.facturacion_actual ?? 0),
            limite_usuarios_equipo: limiteTeam == null ? null : Number(limiteTeam),
            usuarios_equipo_actuales: Number(usadosTeam ?? 0),
            limite_facturas_mes: limiteInv == null ? null : Number(limiteInv),
            facturas_emitidas_mes_actual: Number(usadosInv ?? 0),
            must_complete_checkout: Boolean(json.must_complete_checkout),
            billing_suspended: Boolean(json.billing_suspended),
          });
          return;
        } catch (e: unknown) {
          if (attempt === 0 && isLikelyNetworkFetchError(e)) continue;
          throw e;
        }
      }
    } catch (e: unknown) {
      setError(userFacingFetchFailureMessage(e));
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
