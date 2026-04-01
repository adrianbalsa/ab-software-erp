/**
 * Origen del backend (HTTPS recomendado en prod: `https://api.ablogistics-os.com`).
 * Prioridad: NEXT_PUBLIC_API_BASE_URL → NEXT_PUBLIC_API_URL → NEXT_PUBLIC_API_BASE → localhost.
 * Si el env termina en `/api/v1`, se normaliza (las rutas ya añaden `/api/v1/...`).
 */
import {
  AUTH_TOKEN_KEY,
  authHeaders,
  clearAuthToken,
  getAuthToken,
  setAuthToken,
} from "./auth";
import { getSupabaseBrowserClient } from "./supabase";

export {
  AUTH_TOKEN_KEY,
  authHeaders,
  clearAuthToken,
  getAuthToken,
  setAuthToken,
};

function resolveApiBase(): string {
  const hasExplicitApiBase =
    Boolean(process.env.NEXT_PUBLIC_API_BASE_URL) ||
    Boolean(process.env.NEXT_PUBLIC_API_URL) ||
    Boolean(process.env.NEXT_PUBLIC_API_BASE);
  const raw = (
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.NEXT_PUBLIC_API_BASE ||
    ""
  ).trim();
  if (!raw) {
    if (typeof window !== "undefined") {
      console.error(
        "CRITICAL: NEXT_PUBLIC_API_BASE_URL/NEXT_PUBLIC_API_URL/NEXT_PUBLIC_API_BASE no definidos. Usando fallback http://localhost:8000.",
      );
    } else if (!hasExplicitApiBase) {
      console.error(
        "CRITICAL: API base env vars no definidos en servidor. Usando fallback http://localhost:8000.",
      );
    }
    return "http://localhost:8000";
  }
  let base = raw.replace(/\/$/, "").replace(/\/api\/v1$/i, "");

  // Conmutación robusta por hostname:
  // Si el env apunta a app.ablogistics-os.com, las llamadas de datos deben ir a api.ablogistics-os.com
  // para evitar colisiones con rutas de Next.
  try {
    const u = base.startsWith("http://") || base.startsWith("https://") ? new URL(base) : null;
    if (u && u.hostname.toLowerCase() === "app.ablogistics-os.com") {
      u.hostname = "api.ablogistics-os.com";
      base = u.toString().replace(/\/api\/v1$/i, "");
    }
  } catch {
    // Si no se puede parsear, mantenemos el valor original.
  }
  return base;
}

export const API_BASE = resolveApiBase();

export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers ?? {});
  if (typeof window !== "undefined") {
    let token: string | null = null;
    try {
      const supabase = getSupabaseBrowserClient();
      if (supabase) {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        token = session?.access_token ?? null;
      }
    } catch {
      token = null;
    }
    if (!token) {
      token = getAuthToken();
    }
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const res = await globalThis.fetch(input, { ...init, headers });
  if (res.status === 401 || res.status === 403) {
    if (typeof window !== "undefined") {
      try {
        const supabase = getSupabaseBrowserClient();
        if (supabase) {
          await supabase.auth.signOut();
        }
      } catch {
        /* ignore */
      }
      clearAuthToken();
      window.localStorage.removeItem("token");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login?expired=true";
      }
    }
    throw new Error(`HTTP ${res.status}`);
  }
  return res;
}

// En este módulo, toda llamada fetch usa el wrapper con sesión Supabase.
const fetch = apiFetch;

/**
 * Renueva el access JWT usando la cookie HttpOnly del refresh token.
 * Requiere `credentials: 'include'` también en el login.
 */
/** Mensaje legible desde respuestas FastAPI (`detail`). */
export async function parseApiError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d
        .map((x) => (typeof x === "object" && x && "msg" in x ? String((x as { msg: string }).msg) : ""))
        .filter(Boolean)
        .join(", ");
    }
  } catch {
    /* ignore */
  }
  return `Error HTTP ${res.status}`;
}

/** `empresa_id` del JWT (misma sesión que el backend / RLS). */
export function jwtEmpresaId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const t = getAuthToken();
    if (!t) return null;
    const parts = t.split(".");
    if (parts.length < 2) return null;
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const pad = b64.length % 4 ? "=".repeat(4 - (b64.length % 4)) : "";
    const json = JSON.parse(atob(b64 + pad)) as { empresa_id?: string };
    const eid = json?.empresa_id;
    return typeof eid === "string" && eid.trim() ? eid.trim() : null;
  } catch {
    return null;
  }
}

/** Roles RBAC operativos (claim `rbac_role` del JWT emitido por esta API). */
export type AppRbacRole =
  | "owner"
  | "traffic_manager"
  | "driver"
  | "cliente"
  | "developer";

export function jwtPayload(): Record<string, unknown> | null {
  if (typeof window === "undefined") return null;
  try {
    const t = getAuthToken();
    if (!t) return null;
    const parts = t.split(".");
    if (parts.length < 2) return null;
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const pad = b64.length % 4 ? "=".repeat(4 - (b64.length % 4)) : "";
    return JSON.parse(atob(b64 + pad)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/**
 * Rol efectivo para la UI. Sin JWT → `driver` (menos privilegios) para no mostrar
 * módulos financieros; con JWT sin claim `rbac_role` (legacy) → `owner`.
 */
/** Email o identificador del usuario (`sub` del JWT). */
export function jwtSubject(): string | null {
  const p = jwtPayload();
  const sub = p?.sub;
  return typeof sub === "string" && sub.trim() ? sub.trim() : null;
}

export function jwtRbacRole(): AppRbacRole {
  const p = jwtPayload();
  if (!p) return "driver";
  const r = p?.rbac_role;
  if (
    r === "owner" ||
    r === "traffic_manager" ||
    r === "driver" ||
    r === "cliente" ||
    r === "developer"
  ) {
    return r;
  }
  return "owner";
}

/** Dispara actualización del rol en la misma pestaña (storage solo funciona entre pestañas). */
export const ABL_JWT_UPDATED_EVENT = "abl:jwt-updated";

export function notifyJwtUpdated(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(ABL_JWT_UPDATED_EVENT));
}

/** Portal cliente (autoservicio cargador). */
export type PortalPorteRow = {
  id: string;
  origen: string;
  destino: string;
  fecha_entrega: string | null;
};

export type PortalFacturaRow = {
  id: number;
  numero_factura: string;
  fecha_emision: string;
  total_factura: number;
  estado_pago: string;
};

/** Listado de facturas (alineado con `FacturaOut` y con `VeriFactuBadge`: aeat_sif_*). */
export type Factura = {
  id: number;
  empresa_id?: string;
  numero_factura: string;
  fecha_emision: string;
  total_factura: number;
  hash_registro?: string | null;
  tipo_factura?: string | null;
  is_finalized?: boolean | null;
  fingerprint?: string | null;
  aeat_sif_estado?:
    | "aceptado"
    | "aceptado_con_errores"
    | "rechazado"
    | "error_tecnico"
    | string
    | null;
  aeat_sif_csv?: string | null;
  aeat_sif_descripcion?: string | null;
};

/** Filtros opcionales; `estado_aeat` se envía al backend si el endpoint lo admite. */
export type FacturaFilters = {
  empresa_id?: string;
  /** Coincide con `aeat_sif_estado` (query `estado_aeat` en GET /api/v1/facturas). */
  estado_aeat?: string;
};

export async function getFacturas(filters?: FacturaFilters): Promise<Factura[]> {
  const sp = new URLSearchParams();
  const ea = filters?.estado_aeat?.trim();
  if (ea) sp.set("estado_aeat", ea);
  const qs = sp.toString();
  const url = `${API_BASE}/api/v1/facturas${qs ? `?${qs}` : ""}`;

  async function doFetch(): Promise<Response> {
    return fetch(url, {
      credentials: "include",
      headers: { ...authHeaders() },
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  let rows = (await res.json()) as Factura[];
  const eid = filters?.empresa_id?.trim();
  if (eid) {
    rows = rows.filter((r) => String(r.empresa_id ?? "") === eid);
  }
  return rows;
}

/** Respuesta de ``POST /api/v1/facturas/{id}/enviar`` (envío SMTP). */
export type FacturaEmailEnviadaResponse = {
  factura_id: number;
  numero_factura: string;
  destinatario: string;
  enviado_en: string;
  mensaje: string;
  auditoria?: Record<string, unknown>;
};

/** Error HTTP al enviar factura por correo (incluye ``status`` para 400/503/502). */
export class FacturaEmailSendError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "FacturaEmailSendError";
    this.status = status;
  }
}

/** POST /api/v1/facturas/{id}/enviar — adjunta PDF por SMTP (configuración en el servidor). */
export async function sendFacturaByEmail(facturaId: number): Promise<FacturaEmailEnviadaResponse> {
  const id = encodeURIComponent(String(facturaId));
  const url = `${API_BASE}/api/v1/facturas/${id}/enviar`;
  async function doFetch(): Promise<Response> {
    return fetch(url, {
      method: "POST",
      credentials: "include",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) {
    const msg = await parseApiError(res);
    throw new FacturaEmailSendError(msg, res.status);
  }
  return (await res.json()) as FacturaEmailEnviadaResponse;
}

export type PortalRiskAssessment = {
  score: number;
  creditLimitEur: number;
  collectionTerms: string;
  reasons: string[];
};

export type OnboardingClienteEstado = "PENDING_RISK" | "PENDING_SEPA" | "ACTIVE";

export type OnboardingDashboardRow = {
  id: string;
  nombre: string;
  email: string;
  limite_credito: number;
  estado: OnboardingClienteEstado;
  fecha_invitacion?: string | null;
  riesgo_aceptado?: boolean;
  mandato_activo?: boolean;
  is_blocked?: boolean;
};

export type OnboardingDashboardData = {
  summary: {
    total_clientes: number;
    pendientes_riesgo: number;
    pendientes_sepa: number;
    operativos: number;
  };
  clientes: OnboardingDashboardRow[];
};

async function portalFetchJson<T>(path: string): Promise<T> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}${path}`, {
      credentials: "include",
      headers: { ...authHeaders() },
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
  return (await res.json()) as T;
}

export async function fetchPortalPortes(): Promise<PortalPorteRow[]> {
  return portalFetchJson<PortalPorteRow[]>("/api/v1/portal/portes");
}

export async function fetchPortalFacturas(): Promise<PortalFacturaRow[]> {
  return portalFetchJson<PortalFacturaRow[]>("/api/v1/portal/facturas");
}

export async function fetchPortalMyRisk(): Promise<PortalRiskAssessment> {
  return portalFetchJson<PortalRiskAssessment>("/api/v1/portal/onboarding/my-risk");
}

export async function postPortalAcceptRisk(): Promise<{ status: string; detail: string }> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/portal/onboarding/accept-risk`, {
      method: "POST",
      credentials: "include",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as { status: string; detail: string };
}

export async function fetchClientesOnboardingDashboard(): Promise<OnboardingDashboardData> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/clientes/onboarding-dashboard`, {
      credentials: "include",
      headers: { ...authHeaders() },
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as OnboardingDashboardData;
}

export async function resendClienteInvite(
  clienteId: string,
): Promise<{ message: string }> {
  async function doFetch(): Promise<Response> {
    return fetch(
      `${API_BASE}/api/v1/clientes/${encodeURIComponent(clienteId)}/resend-invite`,
      {
        method: "POST",
        credentials: "include",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
      },
    );
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as { message: string };
}

export function portalAlbaranPdfUrl(porteId: string): string {
  return `${API_BASE}/api/v1/portal/portes/${porteId}/albaran-pdf`;
}

export function portalFacturaPdfUrl(facturaId: number): string {
  return `${API_BASE}/api/v1/portal/facturas/${facturaId}/pdf`;
}

export type SetupMandateOut = {
  redirect_url: string;
  has_active_mandate?: boolean;
};

export async function postPortalSetupMandate(): Promise<SetupMandateOut> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/payments/gocardless/mandates/setup`, {
      method: "POST",
      credentials: "include",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as SetupMandateOut;
}

export type AiChatMessage = { role: "user" | "assistant"; content: string };

export async function postAiChat(payload: {
  message: string;
  history: AiChatMessage[];
  empresa_id?: string | null;
}): Promise<{ reply: string; model?: string | null }> {
  const body: Record<string, unknown> = {
    message: payload.message,
    history: payload.history,
  };
  if (payload.empresa_id) body.empresa_id = payload.empresa_id;

  let res = await fetch(`${API_BASE}/ai/chat`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });

  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) {
      res = await fetch(`${API_BASE}/ai/chat`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(body),
      });
    }
  }

  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
  return (await res.json()) as { reply: string; model?: string | null };
}

export type AdvisorStreamCallbacks = {
  onDelta: (text: string) => void;
  onDone?: (model?: string | null) => void;
  onError?: (message: string) => void;
};

/**
 * POST `/api/v1/chat/advisor` — LogisAdvisor con contexto económico + ESG (SSE).
 */
export async function streamAdvisorChat(
  payload: { message: string; history: AiChatMessage[] },
  cbs: AdvisorStreamCallbacks,
): Promise<void> {
  const body: Record<string, unknown> = {
    message: payload.message,
    history: payload.history,
  };

  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/chat/advisor`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
    });
  }

  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }

  if (!res.ok) {
    cbs.onError?.(await parseApiError(res));
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    cbs.onError?.("No se pudo leer la respuesta en streaming.");
    return;
  }

  const decoder = new TextDecoder();
  let buf = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const chunks = buf.split("\n\n");
      buf = chunks.pop() ?? "";
      for (const block of chunks) {
        const line = block.trim();
        if (!line.startsWith("data:")) continue;
        const raw = line.slice(5).trim();
        try {
          const j = JSON.parse(raw) as {
            text?: string;
            done?: boolean;
            model?: string | null;
            error?: string;
          };
          if (j.error) {
            cbs.onError?.(j.error);
            return;
          }
          if (j.text) cbs.onDelta(j.text);
          if (j.done) cbs.onDone?.(j.model ?? null);
        } catch {
          /* ignore malformed chunk */
        }
      }
    }
  } catch (e) {
    cbs.onError?.(e instanceof Error ? e.message : "Error de red en streaming.");
    return;
  }

  const tail = buf.trim();
  if (tail.startsWith("data:")) {
    const raw = tail.slice(5).trim();
    try {
      const j = JSON.parse(raw) as {
        text?: string;
        done?: boolean;
        model?: string | null;
        error?: string;
      };
      if (j.error) cbs.onError?.(j.error);
      else {
        if (j.text) cbs.onDelta(j.text);
        if (j.done) cbs.onDone?.(j.model ?? null);
      }
    } catch {
      /* ignore */
    }
  }
}

/** Respuesta de POST /api/v1/bancos/conciliar-ai */
export type ConciliarAiResponse = {
  sugerencias_guardadas: number;
  detalle: Array<{
    movimiento_id: string;
    factura_id: number;
    confidence_score: number;
    razonamiento: string;
  }>;
};

/** Movimiento en estado Sugerido (split view conciliación). */
export type MovimientoSugeridoConciliacion = {
  movimiento_id: string;
  fecha: string;
  concepto: string;
  importe: number;
  iban_origen: string | null;
  factura_id: number | null;
  confidence_score: number | null;
  razonamiento_ia: string | null;
  factura_numero: string | null;
  factura_total: number | null;
  factura_fecha: string | null;
  cliente_nombre: string | null;
};

/** Genera y persiste sugerencias IA (movimientos → Sugerido). */
export async function postConciliarAi(): Promise<ConciliarAiResponse> {
  const res = await fetch(`${API_BASE}/api/v1/bancos/conciliar-ai`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    credentials: "include",
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ConciliarAiResponse;
}

export async function getSugerenciasPendientes(): Promise<MovimientoSugeridoConciliacion[]> {
  const res = await fetch(`${API_BASE}/api/v1/bancos/sugerencias-pendientes`, {
    headers: authHeaders(),
    credentials: "include",
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as MovimientoSugeridoConciliacion[];
}

export async function postConfirmarSugerencia(
  movimiento_id: string,
  aprobar: boolean,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/bancos/confirmar-sugerencia`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ movimiento_id, aprobar }),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
}

/** GET /api/v1/treasury/cash-flow */
export type TreasuryCashFlow = {
  saldo_actual_estimado: number;
  cuentas_por_cobrar: number;
  cuentas_por_pagar: number;
  ar_vencimiento_30d: number;
  ap_vencimiento_30d: number;
  proyeccion_30_dias: number;
  waterfall_mes: {
    saldo_inicial: number;
    entradas_cobros: number;
    salidas_pagos: number;
    saldo_final: number;
    mes_label: string;
  };
};

/** GET /api/v1/portes/{id}/cmr-data */
export type CmrPartyBlock = {
  nombre: string | null;
  nif: string | null;
  direccion: string | null;
  pais: string | null;
};

export type CmrLugarFecha = { lugar: string | null; fecha: string | null };

export type CmrMercanciaBlock = {
  descripcion: string | null;
  bultos: number | null;
  peso_kg: number | null;
  peso_ton: number | null;
  volumen_m3: number | null;
  matricula_vehiculo: string | null;
  nombre_vehiculo: string | null;
  nombre_conductor: string | null;
};

export type CmrDataOut = {
  porte_id: string;
  fecha: string;
  km_estimados: number | null;
  casilla_1_remitente: CmrPartyBlock;
  casilla_2_consignatario: CmrPartyBlock;
  casilla_3_lugar_entrega_mercancia: string | null;
  casilla_4_lugar_fecha_toma_carga: CmrLugarFecha;
  casilla_6_12_mercancia: CmrMercanciaBlock;
  casilla_16_transportista: CmrPartyBlock;
  meta: Record<string, unknown>;
};

export async function getPorteCmrData(porteId: string): Promise<CmrDataOut> {
  const res = await fetch(
    `${API_BASE}/api/v1/portes/${encodeURIComponent(porteId)}/cmr-data`,
    { headers: authHeaders(), credentials: "include" },
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as CmrDataOut;
}

/** Respuesta de POST `/api/v1/portes/{id}/firmar-entrega` (POD). */
export type FirmaEntregaOut = {
  porte_id: string;
  estado: string;
  fecha_entrega_real: string;
  odometro_actualizado: boolean;
  odometro_error?: string | null;
};

/** Registra firma del consignatario y marca el porte como Entregado. */
export async function postFirmaEntrega(
  porteId: string,
  body: {
    firma_b64: string;
    nombre_consignatario: string;
    dni_consignatario?: string;
  },
): Promise<FirmaEntregaOut> {
  async function doFetch(): Promise<Response> {
    return fetch(
      `${API_BASE}/api/v1/portes/${encodeURIComponent(porteId)}/firmar-entrega`,
      {
        method: "POST",
        credentials: "include",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as FirmaEntregaOut;
}

/** POST /api/v1/gastos/importar-combustible — CSV combustible (Solred / StarRessa). */
export type FuelImportacionResponse = {
  total_filas_leidas: number;
  filas_importadas_ok: number;
  total_litros: number;
  total_euros: number;
  total_co2_kg: number;
  errores: string[];
};

const LAST_FUEL_IMPORT_STORAGE_KEY = "abl_last_fuel_import_v1";

export function saveLastFuelImport(data: FuelImportacionResponse): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(
      LAST_FUEL_IMPORT_STORAGE_KEY,
      JSON.stringify({ ...data, importedAt: new Date().toISOString() }),
    );
  } catch {
    /* ignore */
  }
}

export function loadLastFuelImport(): (FuelImportacionResponse & { importedAt?: string }) | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(LAST_FUEL_IMPORT_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as FuelImportacionResponse & { importedAt?: string };
  } catch {
    return null;
  }
}

export async function postImportarCombustible(file: File): Promise<FuelImportacionResponse> {
  const form = new FormData();
  form.append("file", file);
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/gastos/importar-combustible`, {
      method: "POST",
      credentials: "include",
      headers: authHeaders(),
      body: form,
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as FuelImportacionResponse;
}

/** GET /api/v1/facturas/{id}/pdf-data — plantilla PDF VeriFactu (@react-pdf/renderer). */
export type FacturaPdfData = {
  factura_id: number;
  numero_factura: string;
  num_factura_verifactu: string | null;
  tipo_factura: string | null;
  fecha_emision: string;
  emisor: { nombre: string; nif: string; direccion: string | null };
  receptor: { nombre: string; nif: string | null };
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
  verifactu_qr_base64: string;
  verifactu_validation_url: string | null;
  verifactu_hash_audit: string;
  fingerprint_completo: string | null;
  hash_registro: string | null;
  aeat_csv_ultimo_envio: string | null;
};

export async function getFacturaPdfData(facturaId: string): Promise<FacturaPdfData> {
  async function doFetch(): Promise<Response> {
    return fetch(
      `${API_BASE}/api/v1/facturas/${encodeURIComponent(facturaId)}/pdf-data`,
      { credentials: "include", headers: authHeaders() },
    );
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as FacturaPdfData;
}

/** GET /api/v1/flota/live-tracking */
export type LiveFleetVehicle = {
  id: string;
  matricula: string;
  estado: "Disponible" | "En Ruta" | "Taller";
  ultima_latitud: number | null;
  ultima_longitud: number | null;
  ultima_actualizacion_gps: string | null;
  conductor_nombre: string | null;
};

export async function getLiveFleetTracking(): Promise<LiveFleetVehicle[]> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/flota/live-tracking`, {
      credentials: "include",
      headers: authHeaders(),
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as LiveFleetVehicle[];
}

export type ExportContableTipo = "ventas" | "compras" | "ambos";
export type ExportContableFormato = "csv" | "excel";

/** Descarga diario contable (CSV/Excel/ZIP); importes con round_fiat en backend. */
export async function downloadAccountingExport(params: {
  fecha_inicio: string;
  fecha_fin: string;
  tipo: ExportContableTipo;
  formato: ExportContableFormato;
}): Promise<void> {
  const sp = new URLSearchParams({
    fecha_inicio: params.fecha_inicio,
    fecha_fin: params.fecha_fin,
    tipo: params.tipo,
    formato: params.formato,
  });
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/export/accounting?${sp.toString()}`, {
      credentials: "include",
      headers: authHeaders(),
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition");
  let name = "export";
  if (cd) {
    const m = /filename="([^"]+)"/.exec(cd);
    const m2 = /filename=([^;\s]+)/.exec(cd);
    if (m) name = m[1];
    else if (m2) name = m2[1].replace(/"/g, "");
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function getTreasuryCashFlow(): Promise<TreasuryCashFlow> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/treasury/cash-flow`, {
      headers: authHeaders(),
      credentials: "include",
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as TreasuryCashFlow;
}

/** GET /api/v1/dashboard/treasury-projection — AR por cubos + PMC */
export type TreasuryProjection = {
  fecha_referencia: string;
  saldo_en_caja: number;
  total_pendiente_cobro: number;
  buckets: { clave: string; etiqueta: string; importe: number }[];
  pmc_dias: number | null;
  pmc_muestras: number;
  pmc_periodo_reciente_dias: number | null;
  pmc_periodo_anterior_dias: number | null;
  pmc_tendencia: "mejorando" | "empeorando" | "estable";
};

export type TreasuryRiskTrendPoint = {
  periodo: string;
  cobrado: number;
  pendiente: number;
};

export type TreasuryRiskResponse = {
  total_pendiente: number;
  garantizado_sepa: number;
  en_riesgo_alto: number;
  cashflow_trend: TreasuryRiskTrendPoint[];
  fuente_datos: "facturas" | "portes" | string;
};

/** GET /api/v1/finance/risk-ranking — ranking V_r por cliente */
export type RiskRankingRow = {
  cliente_id: string;
  nombre: string;
  saldo_pendiente: number;
  riesgo_score: number;
  valor_riesgo: number;
  mandato_sepa_activo: boolean;
};

/** GET /api/v1/finance/margin-ranking — margen neto por ruta (M_n) */
export type RouteMarginRow = {
  ruta: string;
  total_portes: number;
  ingresos_totales: number;
  costes_totales: number;
  margen_neto: number;
  margen_porcentual: number;
};

/** GET /api/v1/finance/credit-alerts — consumo ≥80 % del límite */
export type CreditAlert = {
  cliente_id: string;
  nombre_cliente: string;
  saldo_pendiente: number;
  limite_credito: number;
  porcentaje_consumo: number;
  nivel_alerta: "WARNING" | "CRITICAL";
};

/** GET /api/v1/analytics/cip-matrix — Margen Neto vs Emisiones CO2 */
export type CIPMatrixPoint = {
  ruta: string;
  margen_neto: number;
  emisiones_co2: number;
  total_portes: number;
};

export type FinanceEsgReport = {
  periodo: string;
  total_co2_kg: number;
  total_portes: number;
};

export type SimulationInput = {
  cambio_combustible_pct: number;
  cambio_salarios_pct: number;
  cambio_peajes_pct: number;
};

export type SimulationResult = {
  periodo_meses: number;
  ingresos_base_eur: number;
  gastos_base_eur: number;
  ebitda_base_eur: number;
  ebitda_simulado_eur: number;
  impacto_ebitda_eur: number;
  impacto_ebitda_pct: number;
  impacto_mensual_estimado_eur: number;
  costes_categoria_base: Record<string, number>;
  costes_categoria_simulada: Record<string, number>;
  break_even: {
    tarifa_incremento_pct: number;
    incremento_ingresos_eur: number;
  };
};

export type VerifactuChainAudit = {
  ejercicio: number | null;
  is_valid: boolean;
  total_verified: number;
  factura_id: number | string | null;
  error: string | null;
};

export type VerifactuQrPreview = {
  found: boolean;
  factura_id?: number;
  numero_factura?: string;
  fecha_emision?: string;
  total_factura?: number;
  fingerprint_hash?: string | null;
  /** URL SREI AEAT exactamente codificada en el QR (mismo importe con 2 decimales). */
  aeat_url?: string;
  qr_png_base64?: string;
};

export async function getTreasuryRisk(): Promise<TreasuryRiskResponse> {
  const res = await apiFetch(`${API_BASE}/api/v1/finance/treasury-risk`, {
    credentials: "include",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as TreasuryRiskResponse;
}

export async function getRiskRanking(): Promise<RiskRankingRow[]> {
  const res = await apiFetch(`${API_BASE}/api/v1/finance/risk-ranking`, {
    credentials: "include",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as RiskRankingRow[];
}

export async function getRouteMarginRanking(): Promise<RouteMarginRow[]> {
  const res = await apiFetch(`${API_BASE}/api/v1/finance/margin-ranking`, {
    credentials: "include",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as RouteMarginRow[];
}

export async function getCIPMatrix(): Promise<CIPMatrixPoint[]> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/analytics/cip-matrix`, {
      credentials: "include",
      headers: authHeaders(),
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as CIPMatrixPoint[];
}

export async function postFinancialSimulation(payload: SimulationInput): Promise<SimulationResult> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/analytics/simulate`, {
      method: "POST",
      credentials: "include",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as SimulationResult;
}

export async function getCreditAlerts(): Promise<CreditAlert[]> {
  const res = await apiFetch(`${API_BASE}/api/v1/finance/credit-alerts`, {
    credentials: "include",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as CreditAlert[];
}

export async function getFinanceEsgReport(): Promise<FinanceEsgReport> {
  const res = await apiFetch(`${API_BASE}/api/v1/finance/esg-report`, {
    credentials: "include",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as FinanceEsgReport;
}

export async function downloadFinanceEsgCertificatePdf(): Promise<void> {
  const res = await apiFetch(`${API_BASE}/api/v1/finance/esg-report/download`, {
    credentials: "include",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition");
  let name = "certificado_esg.pdf";
  if (cd) {
    const m = /filename="([^"]+)"/.exec(cd);
    const m2 = /filename=([^;\s]+)/.exec(cd);
    if (m) name = m[1];
    else if (m2) name = m2[1].replace(/"/g, "");
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function getVerifactuChainAudit(
  ejercicio?: number,
): Promise<VerifactuChainAudit> {
  const sp = new URLSearchParams();
  if (typeof ejercicio === "number") sp.set("ejercicio", String(ejercicio));
  async function doFetch(): Promise<Response> {
    const q = sp.toString();
    return fetch(`${API_BASE}/api/v1/verifactu/audit/verify-chain${q ? `?${q}` : ""}`, {
      credentials: "include",
      headers: authHeaders(),
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as VerifactuChainAudit;
}

export async function getVerifactuQrPreview(
  facturaId: number,
): Promise<VerifactuQrPreview> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/verifactu/audit/qr-preview/${encodeURIComponent(String(facturaId))}`, {
      credentials: "include",
      headers: authHeaders(),
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as VerifactuQrPreview;
}

/** Eventos webhook multi-endpoint (catálogo backend). */
export type WebhookEventType =
  | "credit.limit_exceeded"
  | "verifactu.invoice_signed"
  | "esg.certificate_generated";

/** Endpoint registrado (sin `secret_key` en listados). */
export type WebhookEndpoint = {
  id: string;
  empresa_id: string;
  url: string;
  event_types: string[];
  is_active: boolean;
  created_at: string | null;
};

export type WebhookEndpointCreatePayload = {
  url: string;
  /** `['*']` suscribe todos los eventos del catálogo. */
  event_types: WebhookEventType[] | ["*"];
};

export type WebhookEndpointCreated = WebhookEndpoint & { secret_key: string };

async function webhooksFetchJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        ...authHeaders(),
        ...(init?.headers as Record<string, string> | undefined),
      },
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as T;
}

export async function webhooksGetEndpoints(): Promise<WebhookEndpoint[]> {
  return webhooksFetchJson<WebhookEndpoint[]>("/api/v1/webhooks/endpoints");
}

export async function webhooksCreateEndpoint(
  data: WebhookEndpointCreatePayload,
): Promise<WebhookEndpointCreated> {
  return webhooksFetchJson<WebhookEndpointCreated>("/api/v1/webhooks/endpoints", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function webhooksDeleteEndpoint(id: string): Promise<void> {
  async function doFetch(): Promise<Response> {
    return fetch(
      `${API_BASE}/api/v1/webhooks/endpoints/${encodeURIComponent(id)}`,
      {
        method: "DELETE",
        credentials: "include",
        headers: authHeaders(),
      },
    );
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
}

export async function webhooksGetEndpointSecret(id: string): Promise<{ secret_key: string }> {
  return webhooksFetchJson<{ secret_key: string }>(
    `/api/v1/webhooks/endpoints/${encodeURIComponent(id)}/secret`,
  );
}

export const api = {
  clientes: {
    resendInvite: resendClienteInvite,
  },
  facturas: {
    getAll: getFacturas,
    sendByEmail: sendFacturaByEmail,
  },
  finance: {
    fetchTreasuryRisk: getTreasuryRisk,
    getRiskRanking: getRiskRanking,
    getRouteMarginRanking: getRouteMarginRanking,
    getCreditAlerts: getCreditAlerts,
    fetchEsgReport: getFinanceEsgReport,
    downloadEsgCertificatePdf: downloadFinanceEsgCertificatePdf,
  },
  analytics: {
    getCIPMatrix: getCIPMatrix,
    simulateImpact: postFinancialSimulation,
  },
  verifactu: {
    verifyChain: getVerifactuChainAudit,
    getQrPreview: getVerifactuQrPreview,
  },
  webhooks: {
    getEndpoints: webhooksGetEndpoints,
    createEndpoint: webhooksCreateEndpoint,
    deleteEndpoint: webhooksDeleteEndpoint,
    getEndpointSecret: webhooksGetEndpointSecret,
  },
} as const;

export async function getTreasuryProjection(): Promise<TreasuryProjection> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/dashboard/treasury-projection`, {
      credentials: "include",
      headers: authHeaders(),
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as TreasuryProjection;
}

/** GET /api/v1/dashboard/advanced-metrics — KPIs 6 meses (margen, coste/km, ESG). */
export type AdvancedMetricsMonthRow = {
  periodo: string;
  ingresos_facturacion_eur: number;
  gastos_operativos_eur: number;
  margen_contribucion_eur: number;
  km_portes: number;
  gastos_flota_peaje_combustible_eur: number;
  coste_por_km_eur: number | null;
  emisiones_co2_kg: number;
  emisiones_co2_combustible_kg: number;
  emisiones_co2_portes_kg: number;
  ebitda_verde_eur_por_kg_co2: number | null;
};

export type AdvancedMetricsOut = {
  meses: AdvancedMetricsMonthRow[];
  generado_en: string;
  nota_metodologia?: string;
};

export async function getAdvancedMetrics(): Promise<AdvancedMetricsOut> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/dashboard/advanced-metrics`, {
      credentials: "include",
      headers: authHeaders(),
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as AdvancedMetricsOut;
}

/** Eventos suscribibles (alineados con el backend y ejemplos de producto). */
export const WEBHOOK_EVENT_TYPES = [
  "factura.finalizada",
  "porte.facturado",
  "factura.emitida",
  "porte.finalizado",
] as const;

export type WebhookB2BRow = {
  id: string;
  empresa_id: string;
  event_type: string;
  target_url: string;
  is_active: boolean;
  created_at: string;
};

export type WebhookB2BCreated = WebhookB2BRow & { secret_key: string };

export async function listWebhooksB2B(): Promise<WebhookB2BRow[]> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/webhooks/`, {
      credentials: "include",
      headers: authHeaders(),
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as WebhookB2BRow[];
}

export async function createWebhookB2B(body: {
  event_type: string;
  target_url: string;
}): Promise<WebhookB2BCreated> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/webhooks/`, {
      method: "POST",
      credentials: "include",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as WebhookB2BCreated;
}

export async function deleteWebhookB2B(webhookId: string): Promise<void> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/webhooks/${encodeURIComponent(webhookId)}`, {
      method: "DELETE",
      credentials: "include",
      headers: authHeaders(),
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
}

export async function revealWebhookSecret(webhookId: string): Promise<{ secret_key: string }> {
  async function doFetch(): Promise<Response> {
    return fetch(
      `${API_BASE}/api/v1/webhooks/${encodeURIComponent(webhookId)}/secret`,
      {
        credentials: "include",
        headers: authHeaders(),
      },
    );
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as { secret_key: string };
}

export async function testWebhookB2B(webhookId: string): Promise<{ status: string }> {
  async function doFetch(): Promise<Response> {
    return fetch(
      `${API_BASE}/api/v1/webhooks/${encodeURIComponent(webhookId)}/test`,
      {
        method: "POST",
        credentials: "include",
        headers: authHeaders(),
      },
    );
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as { status: string };
}

export type MantenimientoAlertaKm = {
  origen: "plan_km";
  plan_id: string;
  vehiculo_id: string;
  matricula: string | null;
  vehiculo: string | null;
  tipo_tarea: string;
  intervalo_km: number;
  ultimo_km_realizado: number;
  odometro_actual: number;
  km_desde_ultimo: number;
  desgaste: number;
  urgencia: "CRITICO" | "ADVERTENCIA" | "OK";
};

export type MantenimientoAlertaAdmin = {
  origen: "tramite_fecha";
  vehiculo_id: string;
  matricula: string | null;
  vehiculo: string | null;
  tipo_tramite: "ITV" | "SEGURO" | "TACOGRAFO";
  fecha_vencimiento: string;
  dias_restantes: number;
  urgencia: "CRITICO" | "ADVERTENCIA" | "OK";
};

/** Alertas unificadas: mantenimiento por km + trámites administrativos por fecha. */
export type MantenimientoAlerta = MantenimientoAlertaKm | MantenimientoAlertaAdmin;

export function isAlertaKm(a: MantenimientoAlerta): a is MantenimientoAlertaKm {
  return a.origen !== "tramite_fecha";
}

export function isAlertaAdmin(a: MantenimientoAlerta): a is MantenimientoAlertaAdmin {
  return a.origen === "tramite_fecha";
}

export async function getAlertasMantenimiento(): Promise<MantenimientoAlerta[]> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/flota/alertas-mantenimiento`, {
      credentials: "include",
      headers: authHeaders(),
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  const json = (await res.json()) as unknown[];
  return normalizeAlertasMantenimiento(json);
}

/** Compat: respuestas antiguas sin campo `origen` se tratan como plan_km. */
export function normalizeAlertasMantenimiento(
  raw: unknown[],
): MantenimientoAlerta[] {
  return raw.map((row) => {
    const r = row as Record<string, unknown>;
    if (r.origen === "tramite_fecha") {
      return row as MantenimientoAlertaAdmin;
    }
    const km = { ...r } as Record<string, unknown>;
    if (km.origen !== "plan_km") km.origen = "plan_km";
    return km as MantenimientoAlertaKm;
  });
}

export async function postRegistrarMantenimiento(body: {
  plan_id: string;
  importe_eur: number;
  proveedor?: string;
  concepto?: string | null;
}): Promise<{ plan_id: string; ultimo_km_realizado: number; gasto_id: string }> {
  async function doFetch(): Promise<Response> {
    return fetch(`${API_BASE}/api/v1/flota/mantenimiento/registrar`, {
      method: "POST",
      credentials: "include",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as {
    plan_id: string;
    ultimo_km_realizado: number;
    gasto_id: string;
  };
}

export async function refreshAccessToken(): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { access_token?: string };
    const t = data.access_token;
    if (typeof t === "string" && t) {
      try {
        setAuthToken(t);
        notifyJwtUpdated();
      } catch {
        /* ignore */
      }
      return t;
    }
    return null;
  } catch {
    return null;
  }
}
