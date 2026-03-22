"use client";

import { AlertTriangle, CheckCircle2, ShieldAlert } from "lucide-react";

import type { FleetAlert } from "@/hooks/useFleetAlerts";

type Props = {
  alerts: FleetAlert[];
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
};

function borderForPrioridad(p: FleetAlert["prioridad"]): string {
  if (p === "alta") return "border-red-500/80 bg-red-50/90 shadow-sm shadow-red-200/40";
  if (p === "media") return "border-amber-400/90 bg-amber-50/90 shadow-sm shadow-amber-200/40";
  return "border-amber-200/80 bg-slate-50/80";
}

export function AlertasCriticas({ alerts, loading, error, onRetry }: Props) {
  return (
    <section
      className="rounded-2xl border overflow-hidden"
      style={{ borderColor: "#e2e8f0", background: "#fff" }}
    >
      <div
        className="px-6 py-4 flex items-center justify-between gap-3 border-b"
        style={{ borderColor: "#e2e8f0", background: "linear-gradient(90deg, #f8fafc 0%, #eff6ff 100%)" }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <ShieldAlert className="w-5 h-5 shrink-0 text-[#2563eb]" />
          <h2 className="font-bold text-lg truncate" style={{ color: "#0b1224" }}>
            Alertas críticas · Flota
          </h2>
        </div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            disabled={loading}
            className="text-xs font-semibold text-[#2563eb] hover:underline disabled:opacity-50"
          >
            {loading ? "Actualizando…" : "Actualizar"}
          </button>
        )}
      </div>

      <div className="p-6">
        {error && (
          <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2 mb-4">
            {error}
          </p>
        )}

        {loading && (
          <p className="text-sm text-slate-500 py-4">Cargando alertas de flota…</p>
        )}

        {!loading && !error && alerts.length === 0 && (
          <div
            className="flex flex-col items-center justify-center text-center py-10 px-4 rounded-xl border-2 border-dashed"
            style={{ borderColor: "#2563eb40", background: "linear-gradient(180deg, #f0f9ff 0%, #fff 100%)" }}
          >
            <CheckCircle2 className="w-12 h-12 text-emerald-500 mb-3" />
            <p className="text-lg font-bold" style={{ color: "#0b1224" }}>
              Toda la flota está operativa
            </p>
            <p className="text-sm text-slate-600 mt-2 max-w-md">
              No hay ITV, seguros ni revisiones por km en ventana de alerta. Sigue monitorizando desde{" "}
              <span className="font-semibold text-[#2563eb]">Flota</span>.
            </p>
          </div>
        )}

        {!loading && alerts.length > 0 && (
          <ul className="space-y-3">
            {alerts.map((a, idx) => (
              <li
                key={`${a.vehiculo_id}-${a.tipo}-${idx}`}
                className={`rounded-xl border-2 p-4 flex gap-3 ${borderForPrioridad(a.prioridad)}`}
              >
                <div className="shrink-0 pt-0.5">
                  {a.prioridad === "alta" ? (
                    <AlertTriangle className="w-5 h-5 text-red-600" />
                  ) : (
                    <AlertTriangle className="w-5 h-5 text-amber-600" />
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                    {a.tipo === "itv_vencimiento" && "ITV"}
                    {a.tipo === "seguro_vencimiento" && "Seguro"}
                    {a.tipo === "proxima_revision_km" && "Revisión km"}
                    <span className="mx-2">·</span>
                    <span
                      className={
                        a.prioridad === "alta"
                          ? "text-red-700"
                          : a.prioridad === "media"
                            ? "text-amber-800"
                            : "text-slate-600"
                      }
                    >
                      Prioridad {a.prioridad}
                    </span>
                  </p>
                  <p className="font-semibold mt-1" style={{ color: "#0b1224" }}>
                    {[a.matricula, a.vehiculo].filter(Boolean).join(" · ") || "Vehículo"}
                  </p>
                  <p className="text-sm text-slate-700 mt-1">{a.detalle}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
