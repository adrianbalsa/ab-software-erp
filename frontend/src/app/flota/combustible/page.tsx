"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Droplets,
  Fuel,
  Loader2,
  UploadCloud,
} from "lucide-react";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { AppShell } from "@/components/AppShell";
import {
  loadLastFuelImport,
  postImportarCombustible,
  saveLastFuelImport,
  type FuelImportacionResponse,
} from "@/lib/api";

function formatEUR(n: number) {
  return n.toLocaleString("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 2 });
}

function CombustibleImportPage() {
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<(FuelImportacionResponse & { importedAt?: string }) | null>(null);

  useEffect(() => {
    setLast(loadLastFuelImport());
  }, []);

  const upload = useCallback(async (file: File) => {
    setLoading(true);
    setError(null);
    try {
      const data = await postImportarCombustible(file);
      saveLastFuelImport(data);
      setLast({ ...data, importedAt: new Date().toISOString() });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al importar");
    } finally {
      setLoading(false);
    }
  }, []);

  const hasErrores = Boolean(last?.errores?.length);

  return (
    <AppShell active="flota">
      <header className="ab-header flex h-16 shrink-0 items-center justify-between border-b border-slate-200/80 px-6 lg:px-8">
        <div className="flex items-center gap-4 min-w-0">
          <Link
            href="/flota"
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="h-4 w-4 shrink-0" />
            Flota
          </Link>
          <div className="min-w-0">
            <h1 className="text-xl font-bold tracking-tight text-[#0b1224] truncate">
              Importar combustible
            </h1>
            <p className="text-sm text-slate-500 truncate">
              CSV tipo Solred / StarRessa — gastos, ESG y odómetro
            </p>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-4xl space-y-8 px-6 py-8 lg:px-8">
        <section
          className={`rounded-2xl border-2 border-dashed p-8 transition-colors ${
            isDragging
              ? "border-sky-500/70 bg-sky-50"
              : "border-slate-200 bg-white"
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
          <div className="flex flex-col items-center text-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700">
              <UploadCloud className="h-7 w-7" aria-hidden />
            </div>
            <div>
              <p className="text-lg font-semibold text-slate-900">Arrastra y suelta el CSV</p>
              <p className="mt-1 text-sm text-slate-500">
                Columnas: Fecha, Matricula, Litros, Importe_Total; opcionales: Proveedor, Kilometros
              </p>
            </div>
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-[#2563eb] px-5 py-3 text-sm font-bold text-white shadow-sm hover:bg-[#1d4ed8] disabled:opacity-50">
              <Fuel className="h-4 w-4" />
              Elegir archivo CSV / Excel
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
            {loading && (
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <Loader2 className="h-4 w-4 animate-spin text-[#2563eb]" />
                Procesando importación…
              </div>
            )}
          </div>
        </section>

        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
            <div className="flex gap-2">
              <AlertTriangle className="h-5 w-5 shrink-0 text-red-600" />
              {error}
            </div>
          </div>
        )}

        {last && (
          <section className="space-y-4">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">
              Última importación
              {last.importedAt && (
                <span className="ml-2 font-normal normal-case text-slate-400">
                  ({new Date(last.importedAt).toLocaleString("es-ES")})
                </span>
              )}
            </h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Litros importados</p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">
                  {last.total_litros.toLocaleString("es-ES", { maximumFractionDigits: 2 })}
                </p>
                <p className="mt-1 text-xs text-slate-400">Suma de filas correctas</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Euros conciliados</p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">{formatEUR(last.total_euros)}</p>
                <p className="mt-1 text-xs text-slate-400">Importe total registrado en gastos</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">CO₂ registrado (ESG)</p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-emerald-800">
                  {last.total_co2_kg.toLocaleString("es-ES", { maximumFractionDigits: 3 })} kg
                </p>
                <p className="mt-1 text-xs text-slate-400">Según trigger de auditoría</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Filas OK / leídas</p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">
                  {last.filas_importadas_ok} / {last.total_filas_leidas}
                </p>
                <p className="mt-1 text-xs text-slate-400">Incluye filas con avisos</p>
              </div>
            </div>

            {hasErrores && (
              <div className="overflow-hidden rounded-2xl border border-amber-200 bg-amber-50/80">
                <div className="flex items-center gap-2 border-b border-amber-200 bg-amber-100/80 px-4 py-3">
                  <Droplets className="h-5 w-5 text-amber-800" />
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
                      {last.errores.map((msg, i) => (
                        <tr key={`${i}-${msg.slice(0, 24)}`} className="text-amber-950">
                          <td className="px-4 py-2 tabular-nums text-slate-500">{i + 1}</td>
                          <td className="px-4 py-2">{msg}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        )}

        <p className="text-center text-xs text-slate-400">
          Requiere rol administrador o gestor. Los datos se graban con RLS por empresa.
        </p>
      </div>
    </AppShell>
  );
}

export default function Page() {
  return (
    <RoleGuard allowedRoles={["owner", "traffic_manager"]} fallback={<NoAccess />}>
      <CombustibleImportPage />
    </RoleGuard>
  );
}

function NoAccess() {
  return (
    <AppShell active="flota">
      <div className="p-8 text-center text-slate-600">
        <p className="font-semibold text-slate-900">Sin permiso</p>
        <p className="mt-2 text-sm">Solo administradores y gestores pueden importar combustible.</p>
        <Link href="/flota" className="mt-4 inline-block text-[#2563eb] font-semibold hover:underline">
          Volver a Flota
        </Link>
      </div>
    </AppShell>
  );
}
