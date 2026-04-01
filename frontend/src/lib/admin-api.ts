/**
 * Cliente tipado para `/admin/*`. Empresas: siempre `EmpresaOut` en snake_case.
 */
import { API_BASE, apiFetch } from "@/lib/api";
import type { AuditoriaAdminRow, EmpresaCreateBody, MetricasSaaSFacturacionOut, UsuarioAdminOut, UsuarioAdminPatchBody } from "@/types/admin";
import type { EmpresaOut } from "@/types/empresa";

async function adminFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers as Record<string, string>),
    },
  });
  if (res.status === 403) {
    throw new Error("Acceso denegado: se requiere rol administrador.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const d = err?.detail;
    throw new Error(typeof d === "string" ? d : `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function fetchAdminEmpresas(): Promise<EmpresaOut[]> {
  return adminFetch<EmpresaOut[]>("/admin/empresas");
}

export async function createAdminEmpresa(body: EmpresaCreateBody): Promise<EmpresaOut> {
  return adminFetch<EmpresaOut>("/admin/empresas", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function patchAdminEmpresa(
  empresaId: string,
  body: Partial<{ plan: string; activa: boolean; nombre_comercial: string | null }>
): Promise<EmpresaOut> {
  return adminFetch<EmpresaOut>(`/admin/empresas/${encodeURIComponent(empresaId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function fetchAdminUsuarios(): Promise<UsuarioAdminOut[]> {
  return adminFetch<UsuarioAdminOut[]>("/admin/usuarios");
}

export async function patchAdminUsuario(
  usuarioId: string,
  body: UsuarioAdminPatchBody
): Promise<UsuarioAdminOut> {
  return adminFetch<UsuarioAdminOut>(`/admin/usuarios/${encodeURIComponent(usuarioId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function fetchAdminAuditoria(limit = 100): Promise<AuditoriaAdminRow[]> {
  return adminFetch<AuditoriaAdminRow[]>(`/admin/auditoria?limit=${limit}`);
}

export async function fetchAdminMetricasFacturacion(): Promise<MetricasSaaSFacturacionOut> {
  return adminFetch<MetricasSaaSFacturacionOut>("/admin/metricas/facturacion");
}
