"use client";

import React, { useCallback, useMemo, useState } from "react";
import { AlertTriangle, Database } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { BankConnectionCard } from "@/components/finance/BankConnectionCard";
import { ToastHost, type ToastPayload } from "@/components/ui/ToastHost";
import { useBankSync } from "@/hooks/useBankSync";
import { hoursSinceSync } from "@/lib/bankStorage";

export default function FinanceSettingsPage() {
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const bank = useBankSync();
  const { lastSyncAt, hydrated } = bank;

  const pushToast = useCallback((message: string, tone: ToastPayload["tone"]) => {
    setToast({ id: Date.now(), message, tone });
  }, []);

  const onReconciled = useCallback(
    (coincidencias: number) => {
      if (coincidencias <= 0) {
        pushToast(
          "Sincronización correcta. No se han encontrado nuevas coincidencias con facturas pendientes.",
          "info",
        );
        return;
      }
      pushToast(
        `¡Éxito! ${coincidencias} factura${coincidencias === 1 ? "" : "s"} marcada${coincidencias === 1 ? "" : "s"} como cobrada${coincidencias === 1 ? "" : "s"} tras revisar tu banco.`,
        "success",
      );
    },
    [pushToast],
  );

  const staleHours = useMemo(() => hoursSinceSync(lastSyncAt), [lastSyncAt]);
  const showStaleBanner = useMemo(() => {
    if (!hydrated) return false;
    if (lastSyncAt === null) return true;
    return staleHours !== null && staleHours > 48;
  }, [hydrated, lastSyncAt, staleHours]);

  return (
    <AppShell active="dashboard">
      <ToastHost toast={toast} onDismiss={() => setToast(null)} durationMs={6200} />
      <main className="flex-1 flex flex-col overflow-y-auto min-h-0">
        <header className="h-16 ab-header border-b border-slate-200/80 flex items-center justify-between px-8 z-10">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 tracking-tight">
              Ajustes financieros
            </h1>
            <p className="text-sm text-zinc-500 mt-0.5">
              Fuentes de datos para el dashboard económico y la tesorería
            </p>
          </div>
        </header>

        <div className="p-8 space-y-8 max-w-3xl">
          {showStaleBanner && (
            <div
              className="flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-amber-950 shadow-sm"
              role="status"
            >
              <div className="shrink-0 rounded-lg bg-amber-100 p-2 h-fit">
                <AlertTriangle className="h-5 w-5 text-amber-700" aria-hidden />
              </div>
              <div>
                <p className="font-semibold text-amber-950">
                  Tu cash flow puede estar desactualizado
                </p>
                <p className="mt-1 text-sm text-amber-900/90 leading-relaxed">
                  Han pasado más de 48 horas desde la última sincronización bancaria. Vuelve a
                  importar movimientos para alimentar el dashboard económico y detectar cobros con
                  mayor precisión.
                </p>
              </div>
            </div>
          )}

          <section className="space-y-4" aria-labelledby="finance-sources-heading">
            <div className="flex items-center gap-2 text-zinc-800">
              <Database className="h-5 w-5 text-emerald-600" aria-hidden />
              <h2
                id="finance-sources-heading"
                className="text-lg font-bold tracking-tight"
              >
                Fuentes de datos
              </h2>
            </div>
            <p className="text-sm text-zinc-600 leading-relaxed">
              Conecta tu cuenta empresarial mediante Open Banking para sincronizar movimientos y
              conciliar facturas automáticamente. Solo administradores pueden gestionar esta
              conexión.
            </p>

            <BankConnectionCard bank={bank} onReconciled={onReconciled} />
          </section>
        </div>
      </main>
    </AppShell>
  );
}
