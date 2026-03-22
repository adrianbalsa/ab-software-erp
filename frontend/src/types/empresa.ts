import type { UUID } from "./index";

/**
 * Alineado con `EmpresaOut` (FastAPI): solo snake_case en JSON de respuesta.
 * No usar `nombrelegal` / `nombrecomercial` en tipos; eran columnas legacy.
 */
export type EmpresaOut = {
  id: UUID;
  nif: string;
  nombre_legal: string;
  nombre_comercial?: string | null;
  plan: string;
  activa: boolean;
  fecha_registro?: string | null;
  email?: string | null;
  telefono?: string | null;
  direccion?: string | null;
};
