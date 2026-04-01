import axios, { type AxiosRequestConfig, type AxiosResponse } from "axios";
import { createBrowserClient } from "@supabase/ssr";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "https://api.ablogistics-os.com";

export const ABL_JWT_UPDATED_EVENT = "abl:jwt-updated";
export const AUTH_TOKEN_KEY = "sb-access-token";

export const getAuthToken = () =>
  typeof window !== "undefined" ? localStorage.getItem(AUTH_TOKEN_KEY) : null;
export const setAuthToken = (token: string) =>
  typeof window !== "undefined" && localStorage.setItem(AUTH_TOKEN_KEY, token);
export const clearAuthToken = () =>
  typeof window !== "undefined" && localStorage.removeItem(AUTH_TOKEN_KEY);
export const authHeaders = (): Record<string, string> => {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
};
export const notifyJwtUpdated = () => {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(ABL_JWT_UPDATED_EVENT));
  }
};

type JwtPayload = Record<string, unknown>;

export function jwtPayload(): JwtPayload | null {
  try {
    const token = getAuthToken();
    if (!token) return null;
    const parts = token.split(".");
    if (parts.length < 2) return null;
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const pad = "=".repeat((4 - (b64.length % 4)) % 4);
    return JSON.parse(atob(b64 + pad)) as JwtPayload;
  } catch {
    return null;
  }
}

export type AppRbacRole = "owner" | "traffic_manager" | "driver" | "cliente" | "developer";

export function jwtRbacRole(): AppRbacRole {
  const r = jwtPayload()?.rbac_role;
  if (r === "owner" || r === "traffic_manager" || r === "driver" || r === "cliente" || r === "developer") {
    return r;
  }
  return "driver";
}

export function jwtSubject(): string | null {
  const sub = jwtPayload()?.sub;
  return typeof sub === "string" ? sub : null;
}

export function jwtEmpresaId(): string | null {
  const p = jwtPayload();
  const v = p?.empresa_id ?? p?.empresaId ?? p?.tenant_id ?? p?.tenantId;
  return typeof v === "string" ? v : null;
}

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

let _supabaseClient: ReturnType<typeof createBrowserClient> | null = null;
declare global {
  interface Window {
    __supabaseInstance?: ReturnType<typeof createBrowserClient>;
  }
}

export function getSupabaseClient() {
  if (typeof window === "undefined") return null;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anon) return null;

  if (_supabaseClient) return _supabaseClient;
  if (window.__supabaseInstance) {
    _supabaseClient = window.__supabaseInstance;
    return _supabaseClient;
  }

  _supabaseClient = createBrowserClient(url, anon);
  window.__supabaseInstance = _supabaseClient;
  return _supabaseClient;
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

async function resolveAccessToken(): Promise<string | null> {
  const supabase = getSupabaseClient();
  if (!supabase) return getAuthToken();

  const readSessionToken = async (): Promise<string | null> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  };

  let token = await readSessionToken();
  if (!token) {
    await wait(500);
    token = await readSessionToken();
  }
  return token ?? getAuthToken();
}

apiClient.interceptors.request.use(async (config) => {
  let token: string | null = null;
  if (typeof window !== "undefined") {
    token = await resolveAccessToken();
    if (!token) token = window.localStorage.getItem(AUTH_TOKEN_KEY);
  } else {
    try {
      const { cookies } = await import("next/headers");
      const cookieStore = await cookies();
      const refId = process.env.NEXT_PUBLIC_SUPABASE_URL?.split("//")[1]?.split(".")[0];
      const supabaseTokenStr =
        cookieStore.get("sb-access-token")?.value ||
        (refId ? cookieStore.get(`sb-${refId}-auth-token`)?.value : undefined);

      if (supabaseTokenStr) {
        try {
          const parsed = JSON.parse(supabaseTokenStr) as { access_token?: string };
          token = parsed.access_token || supabaseTokenStr;
        } catch {
          token = supabaseTokenStr;
        }
      }
    } catch {
      // Ignorar si no estamos en entorno Next.js SSR
    }
  }
  config.headers = config.headers ?? {};
  const headers = config.headers as Record<string, string>;
  if (token) headers.Authorization = `Bearer ${token}`;
  else delete headers.Authorization;

  return config;
});

export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers ?? {});
  const token = await resolveAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}

export async function parseApiError(res: Response): Promise<string> {
  try {
    const json = (await res.json()) as { detail?: unknown };
    if (typeof json.detail === "string") return json.detail;
  } catch {
    // ignore
  }
  return `Error HTTP ${res.status}`;
}

export type AiChatMessage = { role: "user" | "assistant" | "system"; content: string };
export async function streamAdvisorChat(
  body: { message: string; history?: AiChatMessage[] },
  handlers: { onDelta: (chunk: string) => void; onError?: (msg: string) => void },
): Promise<void> {
  const res = await apiFetch(`${API_BASE}/api/v1/chat/advisor`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    handlers.onError?.(await parseApiError(res));
    return;
  }
  const text = await res.text();
  handlers.onDelta(text);
}

export class FacturaEmailSendError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "FacturaEmailSendError";
    this.status = status;
  }
}
export type Factura = {
  id: number;
  numero_factura?: string;
  cliente_nombre?: string;
  total_factura?: number;
  estado_factura?: string;
  created_at?: string;
  [k: string]: any;
};
export type FacturaPdfData = {
  emisor: { nombre: string; nif?: string | null; direccion?: string | null };
  receptor: { nombre: string; nif?: string | null };
  lineas: Array<{
    concepto: string;
    cantidad: number;
    precio_unitario: number;
    importe: number;
  }>;
  base_imponible: number;
  tipo_iva_porcentaje: number;
  cuota_iva: number;
  total_factura: number;
  verifactu_validation_url?: string;
  hash_encadenado?: string;
  [k: string]: any;
};
export type FacturaPdfPayload = Record<string, any>;
export type CmrDataOut = Record<string, any>;
export type LiveFleetVehicle = Record<string, any>;
export type SimulationInput = Record<string, any>;
export type SimulationResult = Record<string, any>;
export type CIPMatrixPoint = Record<string, any>;
export type VerifactuChainAudit = Record<string, any>;
export type VerifactuQrPreview = Record<string, any>;
export type OnboardingDashboardRow = {
  id: string;
  nombre?: string | null;
  email?: string | null;
  fecha_invitacion?: string | null;
  limite_credito?: number | null;
  riesgo_aceptado?: boolean;
  mandato_activo?: boolean;
  is_blocked?: boolean;
};
export type OnboardingDashboardData = {
  clientes: OnboardingDashboardRow[];
  summary?: {
    total_clientes?: number;
    pendientes_riesgo?: number;
    pendientes_sepa?: number;
    operativos?: number;
  };
};
export type PortalFacturaRow = Record<string, any>;
export type PortalPorteRow = Record<string, any>;
export type FuelImportacionResponse = {
  errores: string[];
  importedAt?: string;
  [k: string]: any;
};
export type MantenimientoUrgencia = "CRITICO" | "ADVERTENCIA" | "OK";
export type MantenimientoAlertaKm = {
  urgencia: MantenimientoUrgencia;
  plan_id: string;
  tipo_tarea: string;
  vehiculo_id: string;
  matricula?: string | null;
  intervalo_km: number;
  km_desde_ultimo: number;
  desgaste: number;
  [k: string]: any;
};
export type MantenimientoAlertaAdmin = {
  urgencia: MantenimientoUrgencia;
  tramite?: string;
  fecha_objetivo?: string | null;
  [k: string]: any;
};
export type MantenimientoAlerta = MantenimientoAlertaKm | MantenimientoAlertaAdmin;
export type MovimientoSugeridoConciliacion = Record<string, any>;
export type ExportContableTipo = string;
export type CreditAlert = Record<string, any>;
export type FinanceEsgReport = Record<string, any>;
export type RiskRankingRow = Record<string, any>;
export type RouteMarginRow = Record<string, any>;
export type TreasuryRiskResponse = {
  total_pendiente?: number;
  garantizado_sepa?: number;
  en_riesgo_alto?: number;
  cashflow_trend: Array<{
    periodo: string;
    cobrado: number;
    pendiente: number;
  }>;
};
export type AdvancedMetricsMonthRow = Record<string, any>;
export type AdvancedMetricsResponse = {
  meses: AdvancedMetricsMonthRow[];
  nota_metodologia?: string | null;
};
export type WebhookEndpoint = Record<string, any>;
export type WebhookB2BRow = Record<string, any>;
export type WebhookEventType = string;

export const WEBHOOK_EVENT_TYPES: WebhookEventType[] = [
  "credit.limit_exceeded",
  "invoice.created",
  "invoice.paid",
  "invoice.overdue",
];

async function getJson<T = any>(url: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(url, init);
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as T;
}

export const refreshAccessToken = async () =>
  getJson<{ access_token?: string }>(`${API_BASE}/auth/refresh`, { method: "POST", credentials: "include" });
export const fetchPortalFacturas = async () => getJson<PortalFacturaRow[]>(`${API_BASE}/api/v1/portal/facturas`);
export const fetchPortalPortes = async () => getJson<PortalPorteRow[]>(`${API_BASE}/api/v1/portal/portes`);
export const fetchPortalMyRisk = async () => getJson(`${API_BASE}/api/v1/portal/onboarding/my-risk`);
export const postPortalAcceptRisk = async (payload: Record<string, any> = {}) =>
  getJson(`${API_BASE}/api/v1/portal/onboarding/accept-risk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
export const postPortalSetupMandate = async () =>
  getJson(`${API_BASE}/api/v1/payments/gocardless/mandates/setup`, { method: "POST" });
export const portalFacturaPdfUrl = (id: string | number) => `${API_BASE}/api/v1/portal/facturas/${id}/pdf`;
export const portalAlbaranPdfUrl = (id: string | number) => `${API_BASE}/api/v1/portal/portes/${id}/albaran-pdf`;
export const getFacturaPdfData = async (id: string | number) =>
  getJson<FacturaPdfData>(`${API_BASE}/api/v1/facturas/${id}/pdf-data`);
export const getPorteCmrData = async (id: string | number) => getJson<CmrDataOut>(`${API_BASE}/api/v1/portes/${id}/cmr`);
export const getLiveFleetTracking = async () =>
  getJson<LiveFleetVehicle[]>(`${API_BASE}/api/v1/flota/live-tracking`);
export const postFirmaEntrega = async (idOrPayload: string | Record<string, any>, maybePayload?: Record<string, any>) => {
  const payload = typeof idOrPayload === "string" ? { id: idOrPayload, ...(maybePayload ?? {}) } : idOrPayload;
  return getJson(`${API_BASE}/api/v1/portes/firma-entrega`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
};
export const getSugerenciasPendientes = async () =>
  getJson<MovimientoSugeridoConciliacion[]>(`${API_BASE}/api/v1/bancos/sugerencias-pendientes`);
export const postConciliarAi = async (payload: Record<string, any> = {}) =>
  getJson(`${API_BASE}/api/v1/bancos/conciliar-ai`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
export const postConfirmarSugerencia = async (
  payloadOrId: Record<string, any> | string,
  aprobar?: boolean,
) => {
  const payload =
    typeof payloadOrId === "string"
      ? { movimiento_id: payloadOrId, aprobar: Boolean(aprobar) }
      : payloadOrId;
  return getJson(`${API_BASE}/api/v1/bancos/confirmar-sugerencia`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
};
export const downloadAccountingExport = async (params: Record<string, string>) => {
  const sp = new URLSearchParams(params).toString();
  const res = await apiFetch(`${API_BASE}/api/v1/export/accounting?${sp}`);
  if (!res.ok) throw new Error(await parseApiError(res));
  return res.blob();
};
export const fetchClientesOnboardingDashboard = async () =>
  getJson<OnboardingDashboardData>(`${API_BASE}/api/v1/clientes/onboarding-dashboard`);
export const loadLastFuelImport = () => {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("abl:last_fuel_import");
  return raw ? (JSON.parse(raw) as FuelImportacionResponse) : null;
};
export const saveLastFuelImport = (value: FuelImportacionResponse) => {
  if (typeof window !== "undefined") localStorage.setItem("abl:last_fuel_import", JSON.stringify(value));
};
export const postImportarCombustible = async (payload: FormData | File) => {
  const body =
    payload instanceof FormData
      ? payload
      : (() => {
          const fd = new FormData();
          fd.append("file", payload);
          return fd;
        })();
  const res = await apiFetch(`${API_BASE}/api/v1/gastos/importar-combustible`, { method: "POST", body });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as FuelImportacionResponse;
};
export const getAlertasMantenimiento = async () =>
  getJson<MantenimientoAlerta[]>(`${API_BASE}/api/v1/flota/alertas-mantenimiento`);
export const isAlertaKm = (row: MantenimientoAlerta): row is MantenimientoAlertaKm =>
  typeof (row as any)?.plan_id === "string";
export const postRegistrarMantenimiento = async (payload: Record<string, any>) =>
  getJson(`${API_BASE}/api/v1/flota/mantenimiento/registrar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
export const getAdvancedMetrics = async () =>
  getJson<AdvancedMetricsResponse>(`${API_BASE}/api/v1/dashboard/advanced-metrics`);
export const listWebhooksB2B = async () => getJson<WebhookB2BRow[]>(`${API_BASE}/api/v1/webhooks/`);
export const createWebhookB2B = async (payload: Record<string, any>) =>
  getJson<WebhookB2BRow>(`${API_BASE}/api/v1/webhooks/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
export const deleteWebhookB2B = async (id: string) =>
  getJson(`${API_BASE}/api/v1/webhooks/${encodeURIComponent(id)}`, { method: "DELETE" });
export const revealWebhookSecret = async (id: string) =>
  getJson<{ secret_key: string }>(`${API_BASE}/api/v1/webhooks/${encodeURIComponent(id)}/secret`);
export const testWebhookB2B = async (id: string) =>
  getJson(`${API_BASE}/api/v1/webhooks/${encodeURIComponent(id)}/test`, { method: "POST" });

export const api = Object.assign(apiClient, {
  facturas: {
    getAll: () => getJson<Factura[]>(`${API_BASE}/facturas`),
    sendByEmail: async (facturaId: number) => {
      const res = await apiFetch(`${API_BASE}/facturas/${facturaId}/send-email`, { method: "POST" });
      if (!res.ok) {
        throw new FacturaEmailSendError(await parseApiError(res), res.status);
      }
      return (await res.json()) as any;
    },
  },
  analytics: {
    getCIPMatrix: () => getJson<CIPMatrixPoint[]>(`${API_BASE}/api/v1/analytics/cip-matrix`),
    simulateImpact: (input: SimulationInput) =>
      getJson<SimulationResult>(`${API_BASE}/api/v1/analytics/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }),
  },
  clientes: {
    resendInvite: (clienteId: string) =>
      getJson(`${API_BASE}/api/v1/clientes/${encodeURIComponent(clienteId)}/resend-invite`, {
        method: "POST",
      }),
  },
  webhooks: {
    getEndpoints: () => listWebhooksB2B(),
    createEndpoint: (payload: Record<string, any>) => createWebhookB2B(payload),
    deleteEndpoint: (id: string) => deleteWebhookB2B(id),
    getEndpointSecret: async (id: string) => {
      const out = await revealWebhookSecret(id);
      return { secret_key: out.secret_key };
    },
  },
  verifactu: {
    verifyChain: (year?: number) =>
      getJson<VerifactuChainAudit>(`${API_BASE}/api/v1/verifactu/audit/verify-chain${year ? `?year=${year}` : ""}`),
    getQrPreview: (facturaId: number) =>
      getJson<VerifactuQrPreview>(
        `${API_BASE}/api/v1/verifactu/audit/qr-preview/${encodeURIComponent(String(facturaId))}`,
      ),
  },
  finance: {
    fetchTreasuryRisk: () => getJson<TreasuryRiskResponse>(`${API_BASE}/api/v1/finance/treasury-risk`),
    getRiskRanking: () => getJson<RiskRankingRow[]>(`${API_BASE}/api/v1/finance/risk-ranking`),
    fetchEsgReport: () => getJson<FinanceEsgReport>(`${API_BASE}/api/v1/finance/esg-report`),
    getCreditAlerts: () => getJson<CreditAlert[]>(`${API_BASE}/api/v1/finance/credit-alerts`),
    getRouteMarginRanking: () =>
      getJson<RouteMarginRow[]>(`${API_BASE}/api/v1/finance/route-margin-ranking`),
    downloadEsgCertificatePdf: async () => {
      const res = await apiFetch(`${API_BASE}/api/v1/finance/esg-certificate/pdf`);
      if (!res.ok) throw new Error(await parseApiError(res));
      return res.blob();
    },
  },
});
export { apiClient };
export default apiClient;

export type ComponentType = any;
export type ReactNode = any;
export type ToastPayload = any;
