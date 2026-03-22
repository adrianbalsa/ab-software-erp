"use client";

import { useCallback, useEffect, useState } from "react";

import {
  formatInstitutionLabel,
  LS_BANK_LAST_SYNC_ISO,
  LS_BANK_OAUTH_DONE,
  readBankInstitutionId,
  readBankLastSync,
  readBankOauthDone,
  writeBankInstitutionId,
  writeBankLastSyncNow,
} from "@/lib/bankStorage";
import { API_BASE, authHeaders, parseApiError } from "@/lib/api";

export type BankConnectOut = {
  link: string;
  requisition_id: string;
};

export type BankSyncOut = {
  transacciones_procesadas: number;
  coincidencias: number;
  detalle: unknown[];
};

function buildConnectUrl(institutionId: string, redirectUrl?: string): string {
  const u = new URL(`${API_BASE}/bank/connect`);
  u.searchParams.set("institution_id", institutionId.trim());
  if (redirectUrl?.trim()) {
    u.searchParams.set("redirect_url", redirectUrl.trim());
  }
  return u.toString();
}

function buildSyncUrl(dateFrom?: string, dateTo?: string): string {
  const u = new URL(`${API_BASE}/bank/sync`);
  if (dateFrom?.trim()) u.searchParams.set("date_from", dateFrom.trim());
  if (dateTo?.trim()) u.searchParams.set("date_to", dateTo.trim());
  return u.toString();
}

export function useBankSync() {
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSyncAt, setLastSyncAt] = useState<Date | null>(null);
  const [institutionId, setInstitutionId] = useState<string | null>(null);
  const [oauthDone, setOauthDone] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setLastSyncAt(readBankLastSync());
    setInstitutionId(readBankInstitutionId());
    setOauthDone(readBankOauthDone());
    setHydrated(true);
  }, []);

  useEffect(() => {
    const refresh = () => {
      setLastSyncAt(readBankLastSync());
      setOauthDone(readBankOauthDone());
      setInstitutionId(readBankInstitutionId());
    };
    const onStorage = (e: StorageEvent) => {
      if (e.key === LS_BANK_LAST_SYNC_ISO || e.key === LS_BANK_OAUTH_DONE) refresh();
    };
    window.addEventListener("focus", refresh);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("focus", refresh);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const isConnected = Boolean(lastSyncAt || oauthDone);

  const fetchConnectLink = useCallback(
    async (institution: string, redirectUrl?: string): Promise<BankConnectOut> => {
      const id = institution.trim();
      if (id.length < 4) {
        throw new Error("Indica un ID de institución válido (GoCardless).");
      }
      setIsLoading(true);
      setError(null);
      try {
        const res = await fetch(buildConnectUrl(id, redirectUrl), {
          method: "GET",
          credentials: "include",
          headers: { ...authHeaders(), Accept: "application/json" },
        });
        if (!res.ok) {
          throw new Error(await parseApiError(res));
        }
        const data = (await res.json()) as BankConnectOut;
        if (!data.link) {
          throw new Error("Respuesta inválida del servidor (sin enlace).");
        }
        writeBankInstitutionId(id);
        setInstitutionId(id);
        return data;
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "No se pudo obtener el enlace de conexión.";
        setError(msg);
        throw e;
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const sync = useCallback(
    async (opts?: { dateFrom?: string; dateTo?: string }): Promise<BankSyncOut> => {
      setIsSyncing(true);
      setError(null);
      try {
        const res = await fetch(buildSyncUrl(opts?.dateFrom, opts?.dateTo), {
          method: "POST",
          credentials: "include",
          headers: { ...authHeaders(), Accept: "application/json" },
        });
        if (!res.ok) {
          throw new Error(await parseApiError(res));
        }
        const data = (await res.json()) as BankSyncOut;
        writeBankLastSyncNow();
        const now = new Date();
        setLastSyncAt(now);
        setOauthDone(true);
        return {
          transacciones_procesadas: data.transacciones_procesadas ?? 0,
          coincidencias: data.coincidencias ?? 0,
          detalle: Array.isArray(data.detalle) ? data.detalle : [],
        };
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Error al sincronizar movimientos.";
        setError(msg);
        throw e;
      } finally {
        setIsSyncing(false);
      }
    },
    [],
  );

  const clearError = useCallback(() => setError(null), []);

  const institutionLabel = formatInstitutionLabel(institutionId);

  return {
    hydrated,
    isLoading,
    isSyncing,
    error,
    clearError,
    lastSyncAt,
    institutionId,
    institutionLabel,
    isConnected,
    fetchConnectLink,
    sync,
  };
}

export type BankSyncApi = ReturnType<typeof useBankSync>;
