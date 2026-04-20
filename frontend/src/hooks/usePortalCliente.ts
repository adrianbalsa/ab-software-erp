"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  apiFetch,
  fetchPortalEsgResumen,
  fetchPortalFacturas,
  fetchPortalPortes,
  fetchPortalPortesActivos,
  parseApiError,
  refreshAccessToken,
  type PortalEsgResumen,
  type PortalFacturaRow,
  type PortalPorteActivoRow,
  type PortalPorteRow,
} from "@/lib/api";

type AsyncState<T> = {
  data: T;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
};

function usePortalResource<T>(loader: () => Promise<T>, initial: T): AsyncState<T> {
  const [data, setData] = useState<T>(initial);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await loader());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cargar");
    } finally {
      setLoading(false);
    }
  }, [loader]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return { data, loading, error, refetch };
}

export function usePortalFacturas(): AsyncState<PortalFacturaRow[]> {
  const loader = useCallback(() => fetchPortalFacturas(), []);
  return usePortalResource(loader, []);
}

export function usePortalPortesEntregados(): AsyncState<PortalPorteRow[]> {
  const loader = useCallback(() => fetchPortalPortes(), []);
  return usePortalResource(loader, []);
}

export function usePortalPortesActivos(options?: { pollMs?: number }): AsyncState<PortalPorteActivoRow[]> {
  const pollMs = options?.pollMs ?? 45_000;
  const loader = useCallback(() => fetchPortalPortesActivos(), []);
  const state = usePortalResource(loader, []);

  useEffect(() => {
    if (pollMs <= 0) return undefined;
    const id = window.setInterval(() => {
      void state.refetch();
    }, pollMs);
    return () => window.clearInterval(id);
  }, [pollMs, state.refetch]);

  return state;
}

export function usePortalEsgResumen(): AsyncState<PortalEsgResumen | null> {
  const loader = useCallback(() => fetchPortalEsgResumen(), []);
  return usePortalResource<PortalEsgResumen | null>(loader, null);
}

export function usePortalClienteOverview() {
  const facturas = usePortalFacturas();
  const entregados = usePortalPortesEntregados();
  const activos = usePortalPortesActivos();
  const esg = usePortalEsgResumen();

  const loading = facturas.loading || entregados.loading || activos.loading || esg.loading;
  const error = facturas.error || entregados.error || activos.error || esg.error;

  const refetchAll = useCallback(async () => {
    await Promise.all([
      facturas.refetch(),
      entregados.refetch(),
      activos.refetch(),
      esg.refetch(),
    ]);
  }, [facturas.refetch, entregados.refetch, activos.refetch, esg.refetch]);

  return useMemo(
    () => ({
      facturas: facturas.data,
      portesEntregados: entregados.data,
      portesActivos: activos.data,
      esg: esg.data,
      loading,
      error,
      refetchAll,
    }),
    [
      facturas.data,
      entregados.data,
      activos.data,
      esg.data,
      loading,
      error,
      refetchAll,
    ],
  );
}

/** Descarga binaria autenticada (PDF/XML) desde rutas `/api/v1/portal/...`. */
export async function portalDownloadFile(url: string, filename: string): Promise<void> {
  async function doFetch(): Promise<Response> {
    return apiFetch(url, { credentials: "include" });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
  const blob = await res.blob();
  const u = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = u;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(u);
}
