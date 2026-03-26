"use client";

import { useMemo, useState } from "react";
import { Loader2, UploadCloud, AlertTriangle, CheckCircle2, X } from "lucide-react";

import {
  postImportarCombustible,
  type FuelImportacionResponse,
} from "@/lib/api";

function formatEUR(n: number) {
  return n.toLocaleString("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 2 });
}

/** @deprecated Usar ``FuelImportacionResponse`` desde ``@/lib/api``. */
export type FuelImportSummary = FuelImportacionResponse;

type Props = {
  open: boolean;
  onClose: () => void;
  onImported?: (summary: FuelImportacionResponse) => void;
};

export function FuelImportModal({ open, onClose, onImported }: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<FuelImportacionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const hasErrores = Boolean(summary?.errores?.length);
  const erroresPreview = useMemo(() => {
    const list = summary?.errores ?? [];
    return list.slice(0, 12);
  }, [summary]);

  async function upload(file: File) {
    setLoading(true);
    setError(null);
    setSummary(null);
    try {
      const json = await postImportarCombustible(file);
      setSummary(json);
      onImported?.(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo importar el combustible");
    } finally {
      setLoading(false);
    }
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-[min(1rem,4vw)]"
      role="dialog"
      aria-modal="true"
      aria-label="Importar combustible"
      onClick={(e) => {
        if (e.target === e.currentTarget && !loading) onClose();
      }}
    >
      <div className="relative flex w-full max-w-3xl max-h-[90vh] flex-col overflow-hidden rounded-2xl border border-slate-800 shadow-2xl">
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-slate-800 px-4 py-3 bg-slate-950/40">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-slate-100 truncate">Importar combustible</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Cruce por matrícula, gastos, ESG (CO₂) y odómetro opcional.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-lg p-2 text-slate-300 hover:bg-slate-800/60 hover:text-white disabled:opacity-50"
            aria-label="Cerrar"
            disabled={loading}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto bg-slate-900/50 p-4 space-y-4">
          <div
            className={`rounded-xl border-2 p-4 transition-colors ${
              isDragging
                ? "border-sky-500/60 bg-sky-500/10"
                : hasErrores
                  ? "border-amber-500/40 bg-amber-500/10"
                  : "border-slate-700 bg-slate-950/20"
            }`}
            onDragEnter={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              const f = e.dataTransfer.files?.[0];
              if (f) void upload(f);
            }}
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5">
                <UploadCloud className="w-5 h-5 text-sky-400" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-slate-100">Arrastra y suelta tu CSV/Excel</p>
                <p className="text-xs text-slate-400 mt-1">
                  Formato:{" "}
                  <span className="font-mono text-slate-200">
                    Fecha, Matricula, Litros, Importe_Total
                  </span>
                  ; opcionales: Proveedor, Kilometros
                </p>
                <div className="mt-3 flex items-center gap-3 flex-wrap">
                  <label className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/20 px-3 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-950/40 cursor-pointer">
                    <UploadCloud className="w-3.5 h-3.5" />
                    Elegir archivo
                    <input
                      type="file"
                      accept=".csv,.xls,.xlsx"
                      className="hidden"
                      disabled={loading}
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) void upload(f);
                      }}
                    />
                  </label>
                  <span className="text-xs text-slate-500">
                    {loading ? "Procesando…" : "Se enviará automáticamente al backend"}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {loading && (
            <div className="ab-card rounded-2xl p-5 border border-slate-800 bg-slate-950/40">
              <div className="flex items-center gap-3">
                <Loader2 className="w-5 h-5 animate-spin text-sky-400" />
                <p className="text-sm font-semibold text-slate-100">Importando y conciliando…</p>
              </div>
              <p className="text-xs text-slate-400 mt-2">
                RLS activo. Matrículas desconocidas aparecen en la tabla de avisos.
              </p>
            </div>
          )}

          {error && (
            <div className="ab-card rounded-2xl border border-red-500/30 bg-red-950/30 p-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-red-400 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-red-200">Error de importación</p>
                  <p className="text-xs text-red-300 mt-1">{error}</p>
                </div>
              </div>
            </div>
          )}

          {summary && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="ab-card rounded-2xl p-4 border border-slate-800 bg-slate-950/40">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Filas OK</p>
                  <p className="text-2xl font-bold text-white tabular-nums mt-1">
                    {summary.filas_importadas_ok} / {summary.total_filas_leidas}
                  </p>
                </div>
                <div className="ab-card rounded-2xl p-4 border border-slate-800 bg-slate-950/40">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Litros</p>
                  <p className="text-2xl font-bold text-white tabular-nums mt-1">
                    {summary.total_litros.toLocaleString("es-ES", { maximumFractionDigits: 2 })}
                  </p>
                </div>
                <div className="ab-card rounded-2xl p-4 border border-slate-800 bg-slate-950/40">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Euros</p>
                  <p className="text-2xl font-bold text-white tabular-nums mt-1">{formatEUR(summary.total_euros)}</p>
                </div>
                <div className="ab-card rounded-2xl p-4 border border-slate-800 bg-slate-950/40">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">CO₂ (kg)</p>
                  <p className="text-2xl font-bold text-emerald-300 tabular-nums mt-1">
                    {summary.total_co2_kg.toLocaleString("es-ES", { maximumFractionDigits: 3 })}
                  </p>
                </div>
              </div>

              {hasErrores ? (
                <div className="ab-card rounded-2xl border border-amber-500/40 bg-amber-950/30 p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-amber-400 mt-0.5 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-amber-200">Avisos de importación</p>
                      <ul className="mt-2 space-y-1 text-xs text-amber-100/90">
                        {erroresPreview.map((m, i) => (
                          <li key={i} className="border-b border-amber-500/20 pb-1 last:border-0">
                            {m}
                          </li>
                        ))}
                      </ul>
                      {summary.errores.length > erroresPreview.length && (
                        <p className="text-xs text-amber-200/70 mt-2">
                          +{summary.errores.length - erroresPreview.length} más (ver página Flota → Combustible).
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="ab-card rounded-2xl border border-emerald-500/30 bg-emerald-950/20 p-4">
                  <div className="flex items-start gap-3">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 mt-0.5" />
                    <div>
                      <p className="text-sm font-semibold text-emerald-200">Importación sin avisos de fila</p>
                      <p className="text-xs text-emerald-200/80 mt-1">
                        Todas las matrículas se cruzaron con la flota o no hubo incidencias reportadas.
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
