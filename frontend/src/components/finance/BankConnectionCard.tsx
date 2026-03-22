"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Building2,
  ExternalLink,
  Landmark,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

import type { BankSyncApi } from "@/hooks/useBankSync";

type Props = {
  bank: BankSyncApi;
  /** Tras POST /bank/sync con éxito (conciliaciones automáticas). */
  onReconciled?: (coincidencias: number) => void;
};

function GoCardlessWordmark() {
  return (
    <div className="flex flex-col items-end sm:items-start gap-0.5 text-right sm:text-left">
      <span className="text-sm font-bold text-[#0c2538] tracking-tight leading-none">
        GoCardless
      </span>
      <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
        Open Banking
      </span>
    </div>
  );
}

export function BankConnectionCard({ bank, onReconciled }: Props) {
  const {
    hydrated,
    isLoading,
    isSyncing,
    error,
    clearError,
    lastSyncAt,
    institutionLabel,
    isConnected,
    fetchConnectLink,
    sync,
    institutionId,
  } = bank;

  const [institutionInput, setInstitutionInput] = useState("");

  useEffect(() => {
    if (hydrated && institutionId) {
      setInstitutionInput(institutionId);
    }
  }, [hydrated, institutionId]);

  const handleConnect = useCallback(async () => {
    clearError();
    const redirectUrl =
      typeof window !== "undefined"
        ? `${window.location.origin}/bancos/callback`
        : undefined;
    try {
      const out = await fetchConnectLink(institutionInput, redirectUrl);
      window.open(out.link, "_blank", "noopener,noreferrer");
    } catch {
      /* error en estado */
    }
  }, [clearError, fetchConnectLink, institutionInput]);

  const handleSync = useCallback(async () => {
    clearError();
    try {
      const out = await sync();
      onReconciled?.(out.coincidencias);
    } catch {
      /* error en estado */
    }
  }, [clearError, onReconciled, sync]);

  if (!hydrated) {
    return (
      <div className="ab-card rounded-2xl p-8 animate-pulse">
        <div className="h-6 w-48 rounded-lg bg-zinc-200" />
        <div className="mt-6 h-24 rounded-xl bg-zinc-100" />
      </div>
    );
  }

  const lastSyncText = lastSyncAt
    ? lastSyncAt.toLocaleString("es-ES", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <div className="ab-card rounded-2xl overflow-hidden border border-zinc-200/90 shadow-sm">
      <div className="border-b border-zinc-100 bg-gradient-to-r from-emerald-50/80 to-zinc-50/50 px-6 py-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-md shadow-emerald-600/20">
            <Landmark className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h3 className="text-base font-bold text-zinc-900 tracking-tight">
              Conexión bancaria
            </h3>
            <p className="text-xs text-zinc-500">
              Datos de solo lectura · Conciliación automática
            </p>
          </div>
        </div>
        <GoCardlessWordmark />
      </div>

      <div className="p-6 space-y-5">
        {error && (
          <div
            className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900"
            role="alert"
          >
            <p className="font-medium">No se pudo completar la operación</p>
            <p className="mt-1 text-red-800/90">{error}</p>
            <button
              type="button"
              onClick={clearError}
              className="mt-2 text-xs font-semibold text-red-700 underline underline-offset-2 hover:text-red-900"
            >
              Cerrar aviso
            </button>
          </div>
        )}

        {!isConnected ? (
          <div className="space-y-5">
            <div className="flex flex-col sm:flex-row gap-4 sm:items-start">
              <div className="flex-1 rounded-xl border border-zinc-200 bg-zinc-50/80 p-4">
                <div className="flex items-start gap-3">
                  <ShieldCheck className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" aria-hidden />
                  <div>
                    <p className="text-sm font-semibold text-zinc-800">
                      Conexión de solo lectura
                    </p>
                    <p className="mt-1 text-sm text-zinc-600 leading-relaxed">
                      Autoriza el acceso en tu banco para importar movimientos y conciliar facturas.
                      No realizamos pagos ni transferencias en tu nombre.
                    </p>
                  </div>
                </div>
              </div>
              <div className="flex flex-col items-center gap-2 sm:w-40 shrink-0">
                <Building2 className="h-10 w-10 text-zinc-400" aria-hidden />
                <span className="text-[10px] uppercase tracking-wider text-zinc-400 text-center">
                  PSD2 / Open Banking
                </span>
              </div>
            </div>

            <div>
              <label
                htmlFor="gocardless-institution"
                className="block text-xs font-semibold uppercase tracking-wide text-zinc-500 mb-2"
              >
                ID de institución (GoCardless)
              </label>
              <input
                id="gocardless-institution"
                className="ab-input font-mono text-sm"
                placeholder="p. ej. SANDBOXFINANCE_SFIN0000"
                value={institutionInput}
                onChange={(e) => setInstitutionInput(e.target.value)}
                autoComplete="off"
              />
              <p className="mt-2 text-xs text-zinc-500">
                Obtén el ID en el{" "}
                <a
                  href="https://bankaccountdata.gocardless.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-emerald-700 hover:text-emerald-800 inline-flex items-center gap-0.5"
                >
                  directorio de bancos
                  <ExternalLink className="h-3 w-3" aria-hidden />
                </a>
                . Tras conectar, vuelve aquí y pulsa <strong>Sincronizar</strong>.
              </p>
            </div>

            <button
              type="button"
              onClick={() => void handleConnect()}
              disabled={isLoading || institutionInput.trim().length < 4}
              className="w-full sm:w-auto min-w-[220px] inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-8 py-3.5 text-base font-semibold text-white shadow-lg shadow-emerald-600/25 hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
                  Generando enlace…
                </>
              ) : (
                <>
                  Conectar banco de empresa
                  <ExternalLink className="h-4 w-4 opacity-90" aria-hidden />
                </>
              )}
            </button>
          </div>
        ) : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                  Banco vinculado
                </p>
                <p className="mt-1 text-lg font-semibold text-zinc-900">
                  {institutionLabel}
                </p>
                <p className="mt-3 text-sm text-zinc-600">
                  <span className="font-medium text-zinc-700">Última sincronización: </span>
                  {lastSyncText ?? (
                    <span className="text-amber-700">Aún no has sincronizado</span>
                  )}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void handleSync()}
                disabled={isSyncing}
                className="inline-flex items-center justify-center gap-2 rounded-xl border-2 border-emerald-600 bg-white px-6 py-3 text-sm font-semibold text-emerald-800 hover:bg-emerald-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
              >
                {isSyncing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin text-emerald-600" aria-hidden />
                    Sincronizando…
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-4 w-4 text-emerald-600" aria-hidden />
                    Sincronizar ahora
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
