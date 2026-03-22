import type { UUID } from "./index";

/** Respuestas `GET /admin/usuarios` — alineado con `UsuarioAdminOut` (snake_case). */
export type UsuarioAdminOut = {
  id: UUID;
  username: string;
  empresa_id: UUID;
  rol: string;
  activo: boolean;
  nombre_completo?: string | null;
  email?: string | null;
  fecha_creacion?: string | null;
};

export type UsuarioAdminPatchBody = {
  rol?: string;
  activo?: boolean;
};

/** `GET /admin/metricas/facturacion` */
export type MetricasSaaSFacturacionOut = {
  total_bruto: number;
  total_iva: number;
  ingreso_neto: number;
  n_facturas: number;
  arpu: number;
};

/** `GET /admin/auditoria` */
export type AuditoriaAdminRow = {
  id?: UUID | null;
  accion?: string | null;
  tabla?: string | null;
  registro_id?: UUID | null;
  empresa_id?: UUID | null;
  timestamp?: string | null;
  fecha?: string | null;
  cambios?: unknown;
};

/** Cuerpo `POST /admin/empresas` (snake_case, compatible con `EmpresaCreate`). */
export type EmpresaCreateBody = {
  nif: string;
  nombre_legal: string;
  nombre_comercial?: string | null;
  plan?: string;
  email?: string | null;
  telefono?: string | null;
  direccion?: string | null;
  activa?: boolean;
};
