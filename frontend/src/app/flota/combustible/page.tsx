"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { AppShell } from "@/components/AppShell";
import { CsvImportWizard } from "@/components/import/CsvImportWizard";
import {
  FUEL_CSV_TEMPLATES,
  FUEL_IMPORT_COLUMN_HINT,
  FuelImportResultPanel,
} from "@/components/import/fuelCsvShared";
import {
  getImportarCombustibleJob,
  loadLastFuelImport,
  postImportarCombustible,
  postImportarCombustibleJob,
  postValidarImportacionCombustible,
  saveLastFuelImport,
  type FuelImportacionResponse,
} from "@/lib/api";

function CombustibleImportPage() {
  const [last, setLast] = useState<(FuelImportacionResponse & { importedAt?: string }) | null>(null);

  useEffect(() => {
    setLast(loadLastFuelImport());
  }, []);

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
            <h1 className="text-xl font-bold tracking-tight text-[#0b1224] truncate">Importar combustible</h1>
            <p className="text-sm text-slate-500 truncate">
              Asistente: plantilla descargable, validación en servidor y resumen
            </p>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-4xl space-y-8 px-6 py-8 lg:px-8">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <CsvImportWizard<FuelImportacionResponse>
            visual="light"
            title="Repostajes (CSV / Excel)"
            subtitle="Compatible con extractos tipo tarjeta profesional (Solred / StarRessa / similares)."
            templates={FUEL_CSV_TEMPLATES}
            prepareExtra={<p className="text-sm text-slate-600 leading-relaxed">{FUEL_IMPORT_COLUMN_HINT}</p>}
            twoPhaseImport={{
              validate: (file, signal) => postValidarImportacionCombustible(file, { signal }),
              commit: (file, signal, idempotencyKey) =>
                postImportarCombustible(file, { signal, idempotencyKey }),
              renderPreview: (s) => <FuelImportResultPanel summary={s} visual="light" />,
              heavyCommitThresholdBytes: 512 * 1024,
              enqueueCommitJob: (f, signal) =>
                postImportarCombustibleJob(f, { signal }).then((r) => ({ jobId: r.job_id })),
              pollCommitJob: (jobId, signal) =>
                getImportarCombustibleJob(jobId, { signal }).then((r) => ({
                  status: r.status,
                  progress: r.progress,
                  result: r.result,
                  error: r.error,
                })),
            }}
            onImported={(data) => {
              saveLastFuelImport(data);
              setLast({ ...data, importedAt: new Date().toISOString() });
            }}
            renderResult={(s) => <FuelImportResultPanel summary={s} visual="light" />}
          />
        </section>

        {last && (
          <section className="space-y-3">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">
              Última importación guardada en este navegador
              {last.importedAt && (
                <span className="ml-2 font-normal normal-case text-slate-400">
                  ({new Date(last.importedAt).toLocaleString("es-ES")})
                </span>
              )}
            </h2>
            <FuelImportResultPanel summary={last} visual="light" erroresMax={500} />
            <p className="text-xs text-slate-400">
              Tras una nueva importación exitosa, puedes reiniciar el asistente con «Nueva importación» arriba.
            </p>
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
