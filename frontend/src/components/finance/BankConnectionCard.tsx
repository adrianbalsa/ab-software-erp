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
  /** Tras POST /api/v1/banking/sync con éxito (conciliaciones automáticas). */
  onReconciled?: (coincidencias: number) => void;
};

function GoCardlessWordmark() {
  return (
    <div className="flex flex-col items-end gap-0.5 text-right sm:items-start sm:text-left">
      <span className="text-sm font-bold leading-none tracking-tight text-zinc-200">
        GoCardless
      </span>
      <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
        Open Banking
      </span>
    </div>
  );
}

const inputDark =
  "w-full rounded-lg border border-zinc-700 bg-zinc-950/60 px-3 py-2.5 font-mono text-sm text-zinc-100 placeholder:text-zinc-500 outline-none transition focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/25";

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
      queueMicrotask(() => {
        setInstitutionInput(institutionId);
      });
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
      <div className="animate-pulse rounded-2xl border border-zinc-800 bg-zinc-900/40 p-8">
        <div className="h-6 w-48 rounded-lg bg-zinc-800" />
        <div className="mt-6 h-24 rounded-xl bg-zinc-800/80" />
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
    <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/40">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 bg-zinc-950/40 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-md shadow-emerald-900/40">
            <Landmark className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h3 className="text-base font-semibold tracking-tight text-zinc-100">Conexión bancaria</h3>
            <p className="text-xs text-zinc-500">Datos de solo lectura · Conciliación automática</p>
          </div>
        </div>
        <GoCardlessWordmark />
      </div>

      <div className="space-y-5 p-6">
        {error && (
          <div
            className="rounded-xl border border-red-500/35 bg-red-950/40 px-4 py-3 text-sm text-red-200"
            role="alert"
          >
            <p className="font-medium">No se pudo completar la operación</p>
            <p className="mt-1 text-red-300/90">{error}</p>
            <button
              type="button"
              onClick={clearError}
              className="mt-2 text-xs font-semibold text-red-400 underline underline-offset-2 hover:text-red-300"
            >
              Cerrar aviso
            </button>
          </div>
        )}

        {!isConnected ? (
          <div className="space-y-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
              <div className="flex-1 rounded-xl border border-zinc-700 bg-zinc-950/40 p-4">
                <div className="flex items-start gap-3">
                  <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" aria-hidden />
                  <div>
                    <p className="text-sm font-semibold text-zinc-100">Conexión de solo lectura</p>
                    <p className="mt-1 text-sm leading-relaxed text-zinc-400">
                      Autoriza el acceso en tu banco para importar movimientos y conciliar facturas. No
                      realizamos pagos ni transferencias en tu nombre.
                    </p>
                  </div>
                </div>
              </div>
              <div className="flex shrink-0 flex-col items-center gap-2 sm:w-40">
                <Building2 className="h-10 w-10 text-zinc-500" aria-hidden />
                <span className="text-center text-[10px] uppercase tracking-wider text-zinc-500">
                  PSD2 / Open Banking
                </span>
              </div>
            </div>

            <div>
              <label
                htmlFor="gocardless-institution"
                className="mb-2 block text-xs font-semibold uppercase tracking-wide text-zinc-500"
              >
                ID de institución (GoCardless)
              </label>
              <input
                id="gocardless-institution"
                className={inputDark}
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
                  className="inline-flex items-center gap-0.5 font-medium text-emerald-500 hover:text-emerald-400"
                >
                  directorio de bancos
                  <ExternalLink className="h-3 w-3" aria-hidden />
                </a>
                . Tras conectar, vuelve aquí y pulsa <strong className="text-zinc-300">Sincronizar</strong>.
              </p>
            </div>

            <button
              type="button"
              onClick={() => void handleConnect()}
              disabled={isLoading || institutionInput.trim().length < 4}
              className="inline-flex min-w-[220px] w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-8 py-3.5 text-base font-semibold text-zinc-950 shadow-lg shadow-emerald-900/30 transition-colors hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
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
                <p className="mt-1 text-lg font-semibold text-zinc-100">{institutionLabel}</p>
                <p className="mt-3 text-sm text-zinc-400">
                  <span className="font-medium text-zinc-300">Última sincronización: </span>
                  {lastSyncText ?? <span className="text-amber-400">Aún no has sincronizado</span>}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void handleSync()}
                disabled={isSyncing}
                className="inline-flex items-center justify-center gap-2 rounded-xl border-2 border-emerald-500/50 bg-zinc-900/60 px-6 py-3 text-sm font-semibold text-emerald-400 transition-colors hover:border-emerald-400 hover:bg-zinc-800/50 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSyncing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin text-emerald-500" aria-hidden />
                    Sincronizando…
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-4 w-4 text-emerald-500" aria-hidden />
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
