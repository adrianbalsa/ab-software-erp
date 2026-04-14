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
      <main className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-zinc-950">
        <header className="z-10 flex h-16 shrink-0 items-center justify-between border-b border-zinc-800 bg-zinc-950/90 px-8 backdrop-blur-md">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">Ajustes financieros</h1>
            <p className="mt-0.5 text-sm text-zinc-400">
              Fuentes de datos para el dashboard económico y la tesorería
            </p>
          </div>
        </header>

        <div className="max-w-3xl space-y-8 p-8">
          {showStaleBanner && (
            <div
              className="flex gap-3 rounded-2xl border border-amber-500/35 bg-amber-950/40 px-4 py-4 text-amber-50"
              role="status"
            >
              <div className="h-fit shrink-0 rounded-lg border border-amber-500/30 bg-amber-950/60 p-2">
                <AlertTriangle className="h-5 w-5 text-amber-400" aria-hidden />
              </div>
              <div>
                <p className="font-semibold text-amber-200">Tu cash flow puede estar desactualizado</p>
                <p className="mt-1 text-sm leading-relaxed text-amber-300/90">
                  Han pasado más de 48 horas desde la última sincronización bancaria. Vuelve a importar
                  movimientos para alimentar el dashboard económico y detectar cobros con mayor precisión.
                </p>
              </div>
            </div>
          )}

          <section className="space-y-4" aria-labelledby="finance-sources-heading">
            <div className="flex items-center gap-2 text-zinc-100">
              <Database className="h-5 w-5 text-emerald-500" aria-hidden />
              <h2 id="finance-sources-heading" className="text-lg font-semibold tracking-tight">
                Fuentes de datos
              </h2>
            </div>
            <p className="text-sm leading-relaxed text-zinc-400">
              Conecta tu cuenta empresarial mediante Open Banking para sincronizar movimientos y conciliar
              facturas automáticamente. Solo administradores pueden gestionar esta conexión.
            </p>

            <BankConnectionCard bank={bank} onReconciled={onReconciled} />
          </section>
        </div>
      </main>
    </AppShell>
  );
}
