/** Borrador de calculadora presupuestos (sessionStorage) para no perder datos tras login. */

export const PRESUPUESTO_DRAFT_KEY = "ab_logistics_presupuesto_draft_v1";

export type PresupuestoDraft = {
  cliente: string;
  nif: string;
  divisa: string;
  metros: number;
  precioM2: number;
  trabajadores: number;
  horas: number;
  costeHora: number;
  materiales: { desc: string; cant: number; precio: number }[];
  margen: number;
  iva: number;
};

export function savePresupuestoDraft(draft: PresupuestoDraft): void {
  try {
    sessionStorage.setItem(PRESUPUESTO_DRAFT_KEY, JSON.stringify(draft));
  } catch {
    /* ignore quota / private mode */
  }
}

export function loadPresupuestoDraft(): PresupuestoDraft | null {
  try {
    const raw = sessionStorage.getItem(PRESUPUESTO_DRAFT_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as PresupuestoDraft;
    if (!p || typeof p !== "object") return null;
    return p;
  } catch {
    return null;
  }
}

export function clearPresupuestoDraft(): void {
  try {
    sessionStorage.removeItem(PRESUPUESTO_DRAFT_KEY);
  } catch {
    /* ignore */
  }
}
