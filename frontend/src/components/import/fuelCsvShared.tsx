"use client";

import { useMemo } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

import type { CsvImportTemplateSpec } from "@/components/import/CsvImportWizard";
import type { FuelImportacionResponse } from "@/lib/api";

export const FUEL_IMPORT_COLUMN_HINT =
  "Columnas: Fecha, Matricula, Litros, Importe_Total; opcionales: Proveedor, Kilometros (odómetro). Separador coma o punto y coma.";

export const FUEL_CSV_TEMPLATES: CsvImportTemplateSpec[] = [
  {
    label: "Plantilla ejemplo (CSV)",
    filename: "plantilla_combustible_ab_logistics.csv",
    body: [
      "Fecha;Matricula;Litros;Importe_Total;Proveedor;Kilometros",
      "2025-01-15;1234ABC;45.2;78.50;Red profesional;120000",
    ].join("\n"),
    withBom: true,
  },
];

function formatEUR(n: number) {
  return n.toLocaleString("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 2 });
}

export type FuelResultVisual = "light" | "dark";

export function FuelImportResultPanel({
  summary,
  visual,
  erroresMax = 200,
}: {
  summary: FuelImportacionResponse;
  visual: FuelResultVisual;
  erroresMax?: number;
}) {
  const hasErrores = Boolean(summary.errores?.length);
  const detalle = summary.errores_detalle ?? [];
  const erroresPreview = useMemo(() => (summary.errores ?? []).slice(0, 12), [summary.errores]);
  const isDark = visual === "dark";
  const simulacion = Boolean(summary.solo_validacion);

  return (
    <div className="space-y-4">
      {simulacion && (
        <div
          className={
            isDark
              ? "rounded-xl border border-sky-500/40 bg-sky-950/40 px-4 py-3 text-xs text-sky-100"
              : "rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-xs text-sky-950"
          }
        >
          <p className="font-semibold">Simulación (sin guardar en base de datos)</p>
          <p className={`mt-1 ${isDark ? "text-sky-200/90" : "text-sky-900/90"}`}>
            Revisa totales y avisos. El CO₂ mostrado es estimación normativa ISO 14083 (2,67 kg/L) hasta la
            importación definitiva, donde aplica el cálculo del vehículo en base de datos.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div
          className={
            isDark
              ? "ab-card rounded-2xl border border-slate-800 bg-slate-950/40 p-4"
              : "rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
          }
        >
          <p
            className={`text-xs font-semibold uppercase tracking-wider ${isDark ? "text-slate-500" : "text-slate-500"}`}
          >
            Filas OK
          </p>
          <p className={`mt-1 text-2xl font-bold tabular-nums ${isDark ? "text-white" : "text-slate-900"}`}>
            {summary.filas_importadas_ok} / {summary.total_filas_leidas}
          </p>
        </div>
        <div
          className={
            isDark
              ? "ab-card rounded-2xl border border-slate-800 bg-slate-950/40 p-4"
              : "rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
          }
        >
          <p
            className={`text-xs font-semibold uppercase tracking-wider ${isDark ? "text-slate-500" : "text-slate-500"}`}
          >
            Litros
          </p>
          <p className={`mt-1 text-2xl font-bold tabular-nums ${isDark ? "text-white" : "text-slate-900"}`}>
            {summary.total_litros.toLocaleString("es-ES", { maximumFractionDigits: 2 })}
          </p>
        </div>
        <div
          className={
            isDark
              ? "ab-card rounded-2xl border border-slate-800 bg-slate-950/40 p-4"
              : "rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
          }
        >
          <p
            className={`text-xs font-semibold uppercase tracking-wider ${isDark ? "text-slate-500" : "text-slate-500"}`}
          >
            Euros
          </p>
          <p className={`mt-1 text-2xl font-bold tabular-nums ${isDark ? "text-white" : "text-slate-900"}`}>
            {formatEUR(summary.total_euros)}
          </p>
        </div>
        <div
          className={
            isDark
              ? "ab-card rounded-2xl border border-slate-800 bg-slate-950/40 p-4"
              : "rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
          }
        >
          <p
            className={`text-xs font-semibold uppercase tracking-wider ${isDark ? "text-slate-500" : "text-slate-500"}`}
          >
            CO₂ (kg)
          </p>
          <p className={`mt-1 text-2xl font-bold tabular-nums ${isDark ? "text-emerald-300" : "text-emerald-800"}`}>
            {summary.total_co2_kg.toLocaleString("es-ES", { maximumFractionDigits: 3 })}
          </p>
          {summary.co2_es_estimacion ? (
            <p className={`mt-1 text-[10px] leading-snug ${isDark ? "text-slate-500" : "text-slate-500"}`}>
              Estimación ISO 14083 (validación)
            </p>
          ) : null}
        </div>
      </div>

      {detalle.length > 0 && (
        <div
          className={
            isDark
              ? "overflow-hidden rounded-xl border border-slate-700 bg-slate-950/50"
              : "overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
          }
        >
          <div
            className={`border-b px-4 py-2 text-xs font-bold uppercase tracking-wider ${isDark ? "border-slate-800 text-slate-400" : "border-slate-100 text-slate-500"}`}
          >
            Detalle estructurado
          </div>
          <div className="max-h-48 overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead className={`sticky top-0 ${isDark ? "bg-slate-900" : "bg-slate-50"} uppercase`}>
                <tr>
                  <th className="px-3 py-2 font-semibold">Fila</th>
                  <th className="px-3 py-2 font-semibold">Código</th>
                  <th className="px-3 py-2 font-semibold">Mensaje</th>
                </tr>
              </thead>
              <tbody className={isDark ? "divide-y divide-slate-800 text-slate-200" : "divide-y divide-slate-100 text-slate-800"}>
                {detalle.slice(0, erroresMax).map((d, i) => (
                  <tr key={`${d.code}-${i}`}>
                    <td className="px-3 py-2 tabular-nums text-slate-500">{d.row ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-[10px]">{d.code}</td>
                    <td className="px-3 py-2">{d.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {hasErrores ? (
        <div
          className={
            isDark
              ? "ab-card rounded-2xl border border-amber-500/40 bg-amber-950/30 p-4"
              : "overflow-hidden rounded-2xl border border-amber-200 bg-amber-50/80"
          }
        >
          {isDark ? (
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" aria-hidden />
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
                  <p className="mt-2 text-xs text-amber-200/70">
                    +{summary.errores.length - erroresPreview.length} más (tabla completa debajo en vista clara).
                  </p>
                )}
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 border-b border-amber-200 bg-amber-100/80 px-4 py-3">
                <AlertTriangle className="h-5 w-5 text-amber-800" aria-hidden />
                <p className="text-sm font-bold text-amber-950">Errores y avisos de importación</p>
              </div>
              <div className="max-h-64 overflow-y-auto">
                <table className="w-full text-left text-sm">
                  <thead className="sticky top-0 bg-amber-50/95 text-xs uppercase text-amber-900/80">
                    <tr>
                      <th className="px-4 py-2 font-semibold">#</th>
                      <th className="px-4 py-2 font-semibold">Mensaje</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-amber-100">
                    {summary.errores.slice(0, erroresMax).map((msg, i) => (
                      <tr key={`${i}-${msg.slice(0, 24)}`} className="text-amber-950">
                        <td className="px-4 py-2 tabular-nums text-slate-500">{i + 1}</td>
                        <td className="px-4 py-2">{msg}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      ) : (
        <div
          className={
            isDark
              ? "ab-card rounded-2xl border border-emerald-500/30 bg-emerald-950/20 p-4"
              : "rounded-2xl border border-emerald-200 bg-emerald-50/90 p-4"
          }
        >
          <div className="flex items-start gap-3">
            <CheckCircle2
              className={`mt-0.5 h-5 w-5 ${isDark ? "text-emerald-400" : "text-emerald-700"}`}
              aria-hidden
            />
            <div>
              <p className={`text-sm font-semibold ${isDark ? "text-emerald-200" : "text-emerald-900"}`}>
                Importación sin avisos de fila
              </p>
              <p className={`mt-1 text-xs ${isDark ? "text-emerald-200/80" : "text-emerald-800/90"}`}>
                Todas las matrículas se cruzaron con la flota o no hubo incidencias reportadas.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
