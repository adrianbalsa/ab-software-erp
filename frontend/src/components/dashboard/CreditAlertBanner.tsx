"use client";

import { AlertCircle, AlertTriangle } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import type { CreditAlert } from "@/lib/api";

function formatEUR2(value: number) {
  return value.toLocaleString("es-ES", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** Barra 0–100 % del consumo; si >100 % el indicador llena la pista. */
function consumptionBarPercent(pct: number) {
  if (!Number.isFinite(pct) || pct < 0) return 0;
  return Math.min(100, pct);
}

export function CreditAlertBanner({ alerts }: { alerts: CreditAlert[] }) {
  if (!alerts.length) return null;

  return (
    <div className="space-y-3" aria-label="Alertas de límite de crédito">
      {alerts.map((a) => {
        const isCritical = a.nivel_alerta === "CRITICAL";
        const message = isCritical
          ? "Límite excedido. Creación de portes bloqueada."
          : "Acercándose al límite de crédito.";

        return (
          <Alert
            key={a.cliente_id}
            className={
              isCritical
                ? "border-red-300 bg-red-50/90 text-red-950 dark:border-red-900 dark:bg-red-950/40 dark:text-red-50"
                : "border-amber-300 bg-amber-50/90 text-amber-950 dark:border-amber-800 dark:bg-amber-950/35 dark:text-amber-50"
            }
          >
            <div className="flex gap-3">
              {isCritical ? (
                <AlertTriangle
                  className="h-5 w-5 shrink-0 text-red-600 dark:text-red-400"
                  aria-hidden
                />
              ) : (
                <AlertCircle
                  className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400"
                  aria-hidden
                />
              )}
              <AlertDescription className="min-w-0 flex-1 space-y-2 pt-0.5">
                <p
                  className={
                    isCritical
                      ? "font-semibold text-red-900 dark:text-red-100"
                      : "font-semibold text-amber-900 dark:text-amber-100"
                  }
                >
                  {message}
                </p>
                <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50">{a.nombre_cliente}</p>
                <p className="text-xs text-zinc-600 dark:text-zinc-400">
                  Pendiente {formatEUR2(a.saldo_pendiente)} · Límite {formatEUR2(a.limite_credito)} ·{" "}
                  <span className="font-medium tabular-nums">{a.porcentaje_consumo.toFixed(2)}%</span>
                </p>
                <Progress
                  className="h-1 w-full bg-zinc-200/80 dark:bg-zinc-800/80"
                  value={consumptionBarPercent(a.porcentaje_consumo)}
                  indicatorClassName={
                    isCritical
                      ? "bg-red-600 dark:bg-red-500"
                      : "bg-amber-500 dark:bg-amber-400"
                  }
                />
              </AlertDescription>
            </div>
          </Alert>
        );
      })}
    </div>
  );
}
