/**
 * Telemetría de producto para importaciones (sin PII de filas CSV).
 * Los consumidores pueden escuchar `abl:import-telemetry` en `window`.
 */
export type ImportTelemetryPayload = {
  event: string;
  wizardSessionId?: string;
  bytes?: number;
  filas_ok?: number;
  filas_tot?: number;
  errores?: number;
  job_id?: string;
  progress?: number;
  error?: string;
};

export function emitImportTelemetry(payload: ImportTelemetryPayload): void {
  if (typeof window === "undefined") return;
  try {
    window.dispatchEvent(new CustomEvent("abl:import-telemetry", { detail: payload }));
  } catch {
    /* ignore */
  }
  try {
    if ((window as unknown as { __ABL_IMPORT_DEBUG?: boolean }).__ABL_IMPORT_DEBUG) {
      console.info("[abl-import]", payload);
    }
  } catch {
    /* ignore */
  }
}
