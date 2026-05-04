"use client";

import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  FileSpreadsheet,
  Loader2,
  UploadCloud,
} from "lucide-react";

import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { importWizardStrings, type ImportWizardStrings } from "@/i18n/importWizard.strings";
import { emitImportTelemetry } from "@/lib/importTelemetry";

export type CsvImportWizardVisual = "light" | "dark";

export type CsvImportTemplateSpec = {
  label: string;
  filename: string;
  /** UTF-8 text (BOM se añade al descargar si ``withBom`` es true). */
  body: string;
  withBom?: boolean;
};

export type CsvImportTwoPhase<TSummary> = {
  validate: (file: File, signal: AbortSignal) => Promise<TSummary>;
  commit: (file: File, signal: AbortSignal, idempotencyKey: string) => Promise<TSummary>;
  renderPreview: (summary: TSummary) => ReactNode;
  /** Por encima de este tamaño (bytes) se usa cola en servidor si hay ``enqueueCommitJob`` + ``pollCommitJob``. */
  heavyCommitThresholdBytes?: number;
  enqueueCommitJob?: (file: File, signal: AbortSignal) => Promise<{ jobId: string }>;
  pollCommitJob?: (
    jobId: string,
    signal: AbortSignal,
  ) => Promise<{
    status: string;
    progress: number;
    result: TSummary | null;
    error: string | null;
  }>;
};

export type CsvImportWizardProps<TSummary> = {
  visual: CsvImportWizardVisual;
  /** Incrementar al reabrir un modal para limpiar estado interno. */
  resetToken?: number;
  title: string;
  subtitle?: string;
  accept?: string;
  templates: CsvImportTemplateSpec[];
  /** Contenido libre bajo el título en el paso 1 (columnas, avisos legales, etc.). */
  prepareExtra?: ReactNode;
  /** Importación en un solo paso (sin validación previa explícita). */
  onImport?: (file: File, signal: AbortSignal) => Promise<TSummary>;
  /** Validar y luego confirmar importación (recomendado para CSV masivos). */
  twoPhaseImport?: CsvImportTwoPhase<TSummary>;
  renderResult: (summary: TSummary) => ReactNode;
  /** Solo tras persistencia real (no tras la fase de validación). */
  onImported?: (summary: TSummary) => void;
  /** Sobrescribe etiquetas i18n por clave. */
  labels?: Partial<ImportWizardStrings>;
};

type Step = 0 | 1 | 2 | 3;

function downloadTemplate(spec: CsvImportTemplateSpec) {
  const raw = spec.withBom !== false ? `\uFEFF${spec.body}` : spec.body;
  const blob = new Blob([raw], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = spec.filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

export function CsvImportWizard<TSummary>({
  visual,
  resetToken = 0,
  title,
  subtitle,
  accept = ".csv,.xls,.xlsx",
  templates,
  prepareExtra,
  onImport,
  twoPhaseImport,
  renderResult,
  onImported,
  labels: labelsProp,
}: CsvImportWizardProps<TSummary>) {
  if (!twoPhaseImport && !onImport) {
    throw new Error("CsvImportWizard: indique ``onImport`` o ``twoPhaseImport``.");
  }

  const { locale } = useOptionalLocaleCatalog();
  const baseL = useMemo(() => importWizardStrings(locale), [locale]);
  const labels = useMemo(() => ({ ...baseL, ...labelsProp }), [baseL, labelsProp]);

  const [step, setStep] = useState<Step>(0);
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewSummary, setPreviewSummary] = useState<TSummary | null>(null);
  const [summary, setSummary] = useState<TSummary | null>(null);
  const [asyncJobPct, setAsyncJobPct] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const wizardSessionIdRef = useRef(
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `wiz-${Date.now()}`,
  );

  const isTwoPhase = Boolean(twoPhaseImport);

  const abortOngoing = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const startAbortable = useCallback(() => {
    abortOngoing();
    const ac = new AbortController();
    abortRef.current = ac;
    return ac;
  }, [abortOngoing]);

  useEffect(() => () => abortOngoing(), [abortOngoing]);

  useEffect(() => {
    abortOngoing();
    setStep(0);
    setFile(null);
    setIsDragging(false);
    setLoading(false);
    setError(null);
    setPreviewSummary(null);
    setSummary(null);
    setAsyncJobPct(null);
    wizardSessionIdRef.current =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `wiz-${Date.now()}`;
  }, [resetToken, abortOngoing]);

  const isDark = visual === "dark";

  const stepDefs = useMemo(() => {
    if (isTwoPhase) {
      return [
        [0, labels.stepPrepare],
        [1, labels.stepFile],
        [2, labels.stepReview],
        [3, labels.stepResult],
      ] as const;
    }
    return [
      [0, labels.stepPrepare],
      [1, labels.stepFile],
      [2, labels.stepResult],
    ] as const;
  }, [isTwoPhase, labels]);

  const stepper = (
    <ol className="flex flex-wrap items-center gap-2 text-xs font-semibold">
      {stepDefs.map(([id, lab], idx) => {
        const active = step === id;
        const done = step > id;
        return (
          <li key={id} className="flex items-center gap-2">
            {idx > 0 && (
              <span className={isDark ? "text-slate-600" : "text-slate-300"} aria-hidden>
                →
              </span>
            )}
            <span
              className={
                active
                  ? isDark
                    ? "text-sky-400"
                    : "text-[#2563eb]"
                  : done
                    ? isDark
                      ? "text-emerald-400/90"
                      : "text-emerald-700"
                    : isDark
                      ? "text-slate-500"
                      : "text-slate-400"
              }
            >
              {idx + 1}. {lab}
            </span>
          </li>
        );
      })}
    </ol>
  );

  const assignFile = useCallback((f: File | undefined | null) => {
    if (!f) return;
    setFile(f);
    setError(null);
    setPreviewSummary(null);
    setSummary(null);
  }, []);

  const runSingleImport = useCallback(async () => {
    if (!file || !onImport) return;
    const ac = startAbortable();
    setLoading(true);
    setError(null);
    emitImportTelemetry({
      event: "wizard_import_sync_start",
      wizardSessionId: wizardSessionIdRef.current,
      bytes: file.size,
    });
    try {
      const s = await onImport(file, ac.signal);
      setSummary(s);
      setStep(2);
      onImported?.(s);
      emitImportTelemetry({
        event: "wizard_import_sync_done",
        wizardSessionId: wizardSessionIdRef.current,
        bytes: file.size,
      });
    } catch (e) {
      if (e instanceof Error && e.name === "AbortError") return;
      const msg = e instanceof Error ? e.message : "Error al importar";
      setError(msg);
      emitImportTelemetry({
        event: "wizard_import_sync_fail",
        wizardSessionId: wizardSessionIdRef.current,
        error: msg,
      });
    } finally {
      setLoading(false);
    }
  }, [file, onImport, onImported, startAbortable]);

  const runValidate = useCallback(async () => {
    if (!file || !twoPhaseImport) return;
    const ac = startAbortable();
    setLoading(true);
    setError(null);
    setPreviewSummary(null);
    emitImportTelemetry({
      event: "wizard_validate_start",
      wizardSessionId: wizardSessionIdRef.current,
      bytes: file.size,
    });
    try {
      const s = await twoPhaseImport.validate(file, ac.signal);
      setPreviewSummary(s);
      setStep(2);
      emitImportTelemetry({
        event: "wizard_validate_done",
        wizardSessionId: wizardSessionIdRef.current,
        bytes: file.size,
      });
    } catch (e) {
      if (e instanceof Error && e.name === "AbortError") return;
      const msg = e instanceof Error ? e.message : "Error al validar";
      setError(msg);
      emitImportTelemetry({
        event: "wizard_validate_fail",
        wizardSessionId: wizardSessionIdRef.current,
        error: msg,
      });
    } finally {
      setLoading(false);
    }
  }, [file, twoPhaseImport, startAbortable]);

  const runCommit = useCallback(async () => {
    if (!file || !twoPhaseImport) return;
    const ac = startAbortable();
    const idem = newIdempotencyKey();
    setLoading(true);
    setError(null);
    setAsyncJobPct(null);
    const tp = twoPhaseImport;
    const thresh = tp.heavyCommitThresholdBytes;
    const useHeavy =
      typeof thresh === "number" &&
      file.size >= thresh &&
      typeof tp.enqueueCommitJob === "function" &&
      typeof tp.pollCommitJob === "function";
    let jobCompleted = false;
    try {
      if (useHeavy) {
        emitImportTelemetry({
          event: "wizard_commit_job_start",
          wizardSessionId: wizardSessionIdRef.current,
          bytes: file.size,
        });
        setAsyncJobPct(1);
        const { jobId } = await tp.enqueueCommitJob!(file, ac.signal);
        const deadline = Date.now() + 12 * 60 * 1000;
        while (Date.now() < deadline) {
          if (ac.signal.aborted) throw new DOMException("Aborted", "AbortError");
          const st = await tp.pollCommitJob!(jobId, ac.signal);
          setAsyncJobPct(st.progress);
          emitImportTelemetry({
            event: "wizard_commit_job_poll",
            wizardSessionId: wizardSessionIdRef.current,
            job_id: jobId,
            progress: st.progress,
          });
          if (st.status === "completed") {
            if (!st.result) throw new Error("Importación completada sin resultado");
            setSummary(st.result);
            setStep(3);
            onImported?.(st.result);
            jobCompleted = true;
            emitImportTelemetry({
              event: "wizard_commit_job_done",
              wizardSessionId: wizardSessionIdRef.current,
              job_id: jobId,
            });
            break;
          }
          if (st.status === "failed") {
            throw new Error(st.error || "Error en importación en segundo plano");
          }
          await new Promise<void>((resolve) => {
            setTimeout(resolve, 750);
          });
        }
        if (!jobCompleted) {
          throw new Error("Tiempo de espera agotado en importación en segundo plano.");
        }
      } else {
        const s = await tp.commit(file, ac.signal, idem);
        setSummary(s);
        setStep(3);
        onImported?.(s);
        emitImportTelemetry({
          event: "wizard_commit_sync_done",
          wizardSessionId: wizardSessionIdRef.current,
          bytes: file.size,
        });
      }
    } catch (e) {
      if (e instanceof Error && e.name === "AbortError") return;
      const msg = e instanceof Error ? e.message : "Error al importar";
      setError(msg);
      emitImportTelemetry({
        event: "wizard_commit_fail",
        wizardSessionId: wizardSessionIdRef.current,
        error: msg,
      });
    } finally {
      setLoading(false);
      setAsyncJobPct(null);
    }
  }, [file, twoPhaseImport, onImported, startAbortable]);

  const shell = isDark
    ? "border-slate-800 bg-slate-950/20 text-slate-100"
    : "border-slate-200 bg-white text-slate-900";

  const dropActive = isDragging
    ? isDark
      ? "border-sky-500/60 bg-sky-500/10"
      : "border-sky-500 bg-sky-50"
    : isDark
      ? "border-slate-700 bg-slate-950/30"
      : "border-slate-200 bg-slate-50/80";

  const primaryFileAction = () => {
    if (isTwoPhase) return void runValidate();
    return void runSingleImport();
  };

  const loadingLabel = isTwoPhase && step === 1 ? labels.validating : labels.committing;

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className={`text-base font-semibold ${isDark ? "text-slate-100" : "text-slate-900"}`}>{title}</h2>
            {subtitle ? (
              <p className={`text-xs mt-0.5 ${isDark ? "text-slate-400" : "text-slate-500"}`}>{subtitle}</p>
            ) : null}
          </div>
        </div>
        <div className="pt-1">{stepper}</div>
      </div>

      {step === 0 && (
        <div className={`rounded-xl border p-4 space-y-4 ${shell}`}>
          {prepareExtra}
          {templates.length > 0 && (
            <div className="space-y-2">
              <p className={`text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-800"}`}>
                {labels.templatesHeading}
              </p>
              <ul className="flex flex-wrap gap-2">
                {templates.map((t) => (
                  <li key={t.filename}>
                    <button
                      type="button"
                      onClick={() => downloadTemplate(t)}
                      className={
                        isDark
                          ? "inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-900/60 px-3 py-2 text-xs font-semibold text-slate-100 hover:bg-slate-800/80"
                          : "inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 shadow-sm hover:bg-slate-50"
                      }
                    >
                      <FileSpreadsheet className="h-3.5 w-3.5 shrink-0 opacity-80" aria-hidden />
                      {t.label}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex justify-end pt-1">
            <button
              type="button"
              onClick={() => setStep(1)}
              className={
                isDark
                  ? "inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-500"
                  : "inline-flex items-center gap-2 rounded-lg bg-[#2563eb] px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-[#1d4ed8]"
              }
            >
              {labels.next}
              <ArrowRight className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="space-y-4">
          <div
            className={`rounded-xl border-2 border-dashed p-4 transition-colors ${dropActive}`}
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
              assignFile(e.dataTransfer.files?.[0]);
            }}
          >
            <div className="flex items-start gap-3">
              <UploadCloud
                className={`mt-0.5 h-6 w-6 shrink-0 ${isDark ? "text-sky-400" : "text-[#2563eb]"}`}
                aria-hidden
              />
              <div className="min-w-0 flex-1 space-y-2">
                <p className={`text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-900"}`}>
                  {labels.dropHint}
                </p>
                {file ? (
                  <p className={`text-xs ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                    <span className="font-semibold">{labels.selectedFile}:</span> {file.name}
                  </p>
                ) : null}
                <label
                  className={
                    isDark
                      ? "inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-600 bg-slate-900/50 px-3 py-2 text-xs font-semibold text-slate-100 hover:bg-slate-800/70"
                      : "inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 shadow-sm hover:bg-slate-50"
                  }
                >
                  {labels.chooseFile}
                  <input
                    type="file"
                    accept={accept}
                    className="hidden"
                    disabled={loading}
                    onChange={(e) => assignFile(e.target.files?.[0])}
                  />
                </label>
              </div>
            </div>
          </div>

          {error && (
            <div
              className={
                isDark
                  ? "rounded-xl border border-red-500/30 bg-red-950/30 p-3"
                  : "rounded-xl border border-red-200 bg-red-50 p-3"
              }
            >
              <div className="flex gap-2">
                <AlertTriangle
                  className={`h-5 w-5 shrink-0 ${isDark ? "text-red-400" : "text-red-600"}`}
                  aria-hidden
                />
                <p className={`text-sm ${isDark ? "text-red-200" : "text-red-900"}`}>{error}</p>
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-2">
            <button
              type="button"
              disabled={loading}
              onClick={() => {
                setStep(0);
                setError(null);
              }}
              className={
                isDark
                  ? "inline-flex items-center gap-2 rounded-lg border border-slate-600 px-3 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-800/60 disabled:opacity-50"
                  : "inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              }
            >
              <ArrowLeft className="h-4 w-4" aria-hidden />
              {labels.back}
            </button>
            <button
              type="button"
              disabled={!file || loading}
              onClick={() => void primaryFileAction()}
              className={
                isDark
                  ? "inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-500 disabled:opacity-40"
                  : "inline-flex items-center gap-2 rounded-lg bg-[#2563eb] px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-[#1d4ed8] disabled:opacity-40"
              }
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  {loadingLabel}
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4" aria-hidden />
                  {isTwoPhase ? labels.validate : labels.import}
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {step === 2 && isTwoPhase && twoPhaseImport && previewSummary != null && (
        <div className="space-y-4">
          {twoPhaseImport.renderPreview(previewSummary)}
          {error && (
            <div
              className={
                isDark
                  ? "rounded-xl border border-red-500/30 bg-red-950/30 p-3"
                  : "rounded-xl border border-red-200 bg-red-50 p-3"
              }
            >
              <div className="flex gap-2">
                <AlertTriangle
                  className={`h-5 w-5 shrink-0 ${isDark ? "text-red-400" : "text-red-600"}`}
                  aria-hidden
                />
                <p className={`text-sm ${isDark ? "text-red-200" : "text-red-900"}`}>{error}</p>
              </div>
            </div>
          )}
          {loading && asyncJobPct != null && (
            <div className="space-y-2">
              <p className={`text-xs font-semibold ${isDark ? "text-sky-200" : "text-sky-900"}`}>
                {labels.backgroundImport}
              </p>
              <progress
                className={isDark ? "h-2.5 w-full accent-sky-500" : "h-2.5 w-full accent-[#2563eb]"}
                value={asyncJobPct}
                max={100}
              />
              <p className={`text-xs tabular-nums ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                {labels.jobProgress}: {asyncJobPct}%
              </p>
            </div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <button
              type="button"
              disabled={loading}
              onClick={() => {
                setStep(1);
                setPreviewSummary(null);
                setError(null);
                setAsyncJobPct(null);
              }}
              className={
                isDark
                  ? "inline-flex items-center gap-2 rounded-lg border border-slate-600 px-3 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-800/60 disabled:opacity-50"
                  : "inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              }
            >
              <ArrowLeft className="h-4 w-4" aria-hidden />
              {labels.back}
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => void runCommit()}
              className={
                isDark
                  ? "inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-40"
                  : "inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-40"
              }
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  {asyncJobPct != null ? labels.backgroundImport : labels.committing}
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4" aria-hidden />
                  {labels.confirmImport}
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {step === 2 && !isTwoPhase && summary != null && (
        <div className="space-y-4">
          {renderResult(summary)}
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setStep(0);
                setFile(null);
                setSummary(null);
                setError(null);
              }}
              className={
                isDark
                  ? "inline-flex items-center gap-2 rounded-lg border border-slate-600 px-3 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-800/60"
                  : "inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              }
            >
              {labels.newImport}
            </button>
          </div>
        </div>
      )}

      {step === 3 && summary != null && (
        <div className="space-y-4">
          {renderResult(summary)}
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setStep(0);
                setFile(null);
                setPreviewSummary(null);
                setSummary(null);
                setError(null);
              }}
              className={
                isDark
                  ? "inline-flex items-center gap-2 rounded-lg border border-slate-600 px-3 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-800/60"
                  : "inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              }
            >
              {labels.newImport}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
