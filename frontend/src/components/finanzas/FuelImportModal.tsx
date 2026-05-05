"use client";

import { useEffect, useState } from "react";

import { CsvImportWizard } from "@/components/import/CsvImportWizard";
import {
  FUEL_CSV_TEMPLATES,
  FUEL_IMPORT_COLUMN_HINT,
  FuelImportResultPanel,
} from "@/components/import/fuelCsvShared";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  getImportarCombustibleJob,
  postImportarCombustible,
  postImportarCombustibleJob,
  postValidarImportacionCombustible,
  type FuelImportacionResponse,
} from "@/lib/api";

/** @deprecated Usar ``FuelImportacionResponse`` desde ``@/lib/api``. */
export type FuelImportSummary = FuelImportacionResponse;

type Props = {
  open: boolean;
  onClose: () => void;
  onImported?: (summary: FuelImportacionResponse) => void;
};

export function FuelImportModal({ open, onClose, onImported }: Props) {
  const [resetToken, setResetToken] = useState(0);

  useEffect(() => {
    if (!open) return;
    const id = requestAnimationFrame(() => setResetToken((t) => t + 1));
    return () => cancelAnimationFrame(id);
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent
        className="max-h-[90vh] max-w-3xl overflow-hidden border-slate-800 bg-slate-950 p-0 shadow-2xl"
        aria-describedby="fuel-import-wizard-desc"
      >
        <DialogHeader className="border-b border-slate-800 bg-slate-950/80 px-5 py-4">
          <DialogTitle className="text-base font-semibold text-slate-100">Importar combustible</DialogTitle>
          <DialogDescription id="fuel-import-wizard-desc" className="text-xs text-slate-400">
            Validación previa sin guardar; confirmación con idempotencia HTTP (Redis) si está configurada.
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[calc(90vh-7rem)] overflow-y-auto px-5 py-4 bg-slate-900/50">
          <CsvImportWizard<FuelImportacionResponse>
            resetToken={resetToken}
            visual="dark"
            title="CSV / Excel de combustible"
            subtitle="Cruce por matrícula, gastos, ESG (CO₂) y odómetro opcional."
            templates={FUEL_CSV_TEMPLATES}
            prepareExtra={<p className="text-xs text-slate-400 leading-relaxed">{FUEL_IMPORT_COLUMN_HINT}</p>}
            twoPhaseImport={{
              validate: (file, signal) => postValidarImportacionCombustible(file, { signal }),
              commit: (file, signal, idempotencyKey) =>
                postImportarCombustible(file, { signal, idempotencyKey }),
              renderPreview: (s) => <FuelImportResultPanel summary={s} visual="dark" />,
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
            renderResult={(s) => <FuelImportResultPanel summary={s} visual="dark" />}
            onImported={onImported}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
