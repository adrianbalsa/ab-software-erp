"use client";

import { useMemo, useState } from "react";
import { Download, FileSpreadsheet, Loader2 } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { downloadAccountingExport, type ExportContableTipo } from "@/lib/api";

function defaultDates() {
  const end = new Date();
  const start = new Date(end.getFullYear(), end.getMonth(), 1);
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  return { inicio: iso(start), fin: iso(end) };
}

export default function ExportarContablePage() {
  const defaults = useMemo(() => defaultDates(), []);
  const [inicio, setInicio] = useState(defaults.inicio);
  const [fin, setFin] = useState(defaults.fin);
  const [tipo, setTipo] = useState<ExportContableTipo>("ventas");
  const [loading, setLoading] = useState<"csv" | "excel" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(fmt: "csv" | "excel") {
    setError(null);
    setLoading(fmt);
    try {
      await downloadAccountingExport({
        fecha_inicio: inicio,
        fecha_fin: fin,
        tipo,
        formato: fmt,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al exportar");
    } finally {
      setLoading(null);
    }
  }

  return (
    <AppShell active="exportar">
      <RoleGuard
        allowedRoles={["owner"]}
        fallback={
          <main className="p-8">
            <p className="text-slate-500">
              La exportación contable solo está disponible para administradores.
            </p>
          </main>
        }
      >
        <header className="h-16 ab-header border-b border-slate-800/80 flex items-center justify-between px-8 z-10 shrink-0 bg-[#0a0f1a]/90 backdrop-blur-sm">
          <div>
            <h1 className="text-2xl font-bold text-slate-100 tracking-tight">
              Exportación contable
            </h1>
            <p className="text-sm text-slate-500">
              Diario de ventas / compras (CSV para A3/Sage, Excel con hojas separadas)
            </p>
          </div>
        </header>

        <main
          className="p-8 flex-1 overflow-y-auto max-w-xl mx-auto w-full"
          style={{
            background:
              "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(37, 99, 235, 0.08), transparent), #020617",
          }}
        >
          {error && (
            <div
              className="mb-6 rounded-xl border px-4 py-3 text-sm text-red-200"
              style={{
                background: "rgba(127, 29, 29, 0.25)",
                borderColor: "rgba(248, 113, 113, 0.35)",
              }}
            >
              {error}
            </div>
          )}

          <div
            className="rounded-2xl border border-slate-700/80 p-6 space-y-6"
            style={{
              background:
                "linear-gradient(145deg, rgba(15, 23, 42, 0.95) 0%, rgba(2, 6, 23, 0.98) 100%)",
            }}
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Fecha inicio
                </span>
                <input
                  type="date"
                  value={inicio}
                  onChange={(e) => setInicio(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100"
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Fecha fin
                </span>
                <input
                  type="date"
                  value={fin}
                  onChange={(e) => setFin(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100"
                />
              </label>
            </div>

            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Tipo de diario
              </span>
              <select
                value={tipo}
                onChange={(e) => setTipo(e.target.value as ExportContableTipo)}
                className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100"
              >
                <option value="ventas">Ventas (facturas emitidas)</option>
                <option value="compras">Gastos / compras</option>
                <option value="ambos">Ventas y compras</option>
              </select>
            </label>

            <p className="text-xs text-slate-500 leading-relaxed">
              Los importes se redondean en servidor a 2 decimales (motor fiat). Si eliges ambos en
              CSV, se descarga un ZIP con dos archivos.
            </p>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                disabled={loading !== null}
                onClick={() => void run("excel")}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold px-4 py-2.5"
              >
                {loading === "excel" ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <FileSpreadsheet className="w-4 h-4" />
                )}
                Descargar Excel
              </button>
              <button
                type="button"
                disabled={loading !== null}
                onClick={() => void run("csv")}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-800/90 hover:bg-slate-700 disabled:opacity-50 text-slate-100 text-sm font-semibold px-4 py-2.5"
              >
                {loading === "csv" ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Download className="w-4 h-4" />
                )}
                Descargar CSV (A3 / Sage)
              </button>
            </div>
          </div>
        </main>
      </RoleGuard>
    </AppShell>
  );
}
