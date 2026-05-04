import { API_BASE, apiFetch } from "@/lib/api";
import { normalizePlanQueryParam } from "@/lib/productPlans";

export type EmpresaQuotaGate = {
  must_complete_checkout?: boolean;
  billing_suspended?: boolean;
  /** Slug canónico devuelto por `GET /empresa/quota` (`starter` | `pro` | `enterprise`). */
  plan_type?: string;
};

type QuotaRead =
  | { tag: "unauth" }
  | { tag: "fail"; status: number }
  | { tag: "ok"; data: Record<string, unknown> };

async function readEmpresaQuota(): Promise<QuotaRead> {
  const res = await apiFetch(`${API_BASE}/empresa/quota`, { credentials: "include" });
  if (res.status === 401) return { tag: "unauth" };
  if (!res.ok) return { tag: "fail", status: res.status };
  try {
    const data = (await res.json()) as Record<string, unknown>;
    return { tag: "ok", data };
  } catch {
    return { tag: "fail", status: res.status };
  }
}

/**
 * Próxima ruta tras sesión válida: checkout si falta suscripción, facturación si hay suspensión,
 * dashboard si el tenant está operativo, u onboarding si no hay cuota (p. ej. sin empresa).
 */
export async function resolvePostAuthNavigation(noTenantPath = "/onboarding"): Promise<string> {
  const r = await readEmpresaQuota();
  if (r.tag === "unauth") return "/login";
  if (r.tag !== "ok") return noTenantPath;
  if (Boolean(r.data.billing_suspended)) return "/dashboard/settings/billing";
  if (Boolean(r.data.must_complete_checkout)) {
    const planSlug = normalizePlanQueryParam(
      typeof r.data.plan_type === "string" ? r.data.plan_type : "starter",
    );
    return `/payments/create-checkout?plan=${encodeURIComponent(planSlug)}&source=resume`;
  }
  return "/dashboard";
}

/** null = sin cuota legible (401, error de red o sin empresa). */
export async function fetchEmpresaQuotaGate(): Promise<EmpresaQuotaGate | null> {
  const r = await readEmpresaQuota();
  if (r.tag !== "ok") return null;
  return {
    must_complete_checkout: Boolean(r.data.must_complete_checkout),
    billing_suspended: Boolean(r.data.billing_suspended),
    plan_type: typeof r.data.plan_type === "string" ? r.data.plan_type : undefined,
  };
}
