/** Claves localStorage para estado de Open Banking (solo cliente; el backend es la fuente de verdad en sync). */

export const LS_BANK_INSTITUTION_ID = "abl_bank_institution_id";
export const LS_BANK_LAST_SYNC_ISO = "abl_bank_last_sync_iso";
export const LS_BANK_OAUTH_DONE = "abl_bank_oauth_done";

export function readBankInstitutionId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const v = localStorage.getItem(LS_BANK_INSTITUTION_ID);
    return v && v.trim() ? v.trim() : null;
  } catch {
    return null;
  }
}

export function readBankLastSync(): Date | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(LS_BANK_LAST_SYNC_ISO);
    if (!raw) return null;
    const d = new Date(raw);
    return Number.isNaN(d.getTime()) ? null : d;
  } catch {
    return null;
  }
}

export function readBankOauthDone(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(LS_BANK_OAUTH_DONE) === "1";
  } catch {
    return false;
  }
}

export function writeBankInstitutionId(id: string): void {
  try {
    localStorage.setItem(LS_BANK_INSTITUTION_ID, id.trim());
  } catch {
    /* ignore */
  }
}

export function writeBankLastSyncNow(): void {
  try {
    localStorage.setItem(LS_BANK_LAST_SYNC_ISO, new Date().toISOString());
  } catch {
    /* ignore */
  }
}

export function writeBankOauthDone(): void {
  try {
    localStorage.setItem(LS_BANK_OAUTH_DONE, "1");
  } catch {
    /* ignore */
  }
}

/** Nombres legibles para IDs frecuentes (GoCardless Bank Account Data). */
export function formatInstitutionLabel(institutionId: string | null): string {
  if (!institutionId) return "Banco conectado";
  const known: Record<string, string> = {
    SANDBOXFINANCE_SFIN0000: "Sandbox (GoCardless)",
    SANDBOXFINANCE_SFIN0001: "Sandbox alternativo",
  };
  return known[institutionId] ?? institutionId.replace(/_/g, " ");
}

export function hoursSinceSync(last: Date | null): number | null {
  if (!last) return null;
  return (Date.now() - last.getTime()) / (1000 * 60 * 60);
}
