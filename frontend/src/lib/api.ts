import axios, { type AxiosRequestConfig, type AxiosResponse } from "axios";
import { createBrowserClient } from "@supabase/ssr";
import { z, type ZodSchema } from "zod";
import { getAuthToken as getAuthTokenFromStore } from "@/lib/auth";
import { resolveApiBase } from "@/lib/api-base";

export const API_BASE = resolveApiBase();

export const ABL_JWT_UPDATED_EVENT = "abl:jwt-updated";

export class ApiValidationError extends Error {
  readonly payload: unknown;
  readonly issues: z.ZodIssue[];

  constructor(message: string, payload: unknown, issues: z.ZodIssue[]) {
    super(message);
    this.name = "ApiValidationError";
    this.payload = payload;
    this.issues = issues;
  }
}

/**
 * JWT: localStorage (`abl_auth_token`) si el login lo guardó; OAuth usa cookie HttpOnly en la API.
 * Peticiones con `credentials: 'include'` envían la cookie; el backend acepta Bearer o cookie.
 * En RSC/SSR: `cookies().get("abl_auth_token")` — ver `getSessionAccessTokenForRole` en `server-api.ts`.
 */
export function getAuthToken(): string | null {
  const t = getAuthTokenFromStore();
  if (t) return t;
  if (typeof window !== "undefined") {
    return localStorage.getItem("sb-access-token");
  }
  return null;
}

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

/** Decodifica el segmento payload (2.º fragmento) de un JWT; Node (Buffer) o navegador (atob). */
export function decodeJwtPayloadSegment(segment: string): JwtPayload | null {
  try {
    const b64 = segment.replace(/-/g, "+").replace(/_/g, "/");
    const pad = "=".repeat((4 - (b64.length % 4)) % 4);
    const padded = b64 + pad;
    let json: string;
    if (typeof Buffer !== "undefined") {
      json = Buffer.from(padded, "base64").toString("utf8");
    } else if (typeof globalThis.atob === "function") {
      json = globalThis.atob(padded);
    } else {
      return null;
    }
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}

export function jwtPayloadFromAccessToken(token: string | null | undefined): JwtPayload | null {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length < 2) return null;
  return decodeJwtPayloadSegment(parts[1]);
}

export function jwtPayload(): JwtPayload | null {
  return jwtPayloadFromAccessToken(getAuthToken());
}

export type AppRbacRole =
  | "owner"
  | "admin"
  | "traffic_manager"
  | "driver"
  | "cliente"
  | "developer";

/** Owner o admin de empresa (mismos privilegios de shell / facturación). */
export function isOwnerLike(role: AppRbacRole): boolean {
  return role === "owner" || role === "admin";
}

/** Rol operativo sin acceso a finanzas / Búnker fiscal en navegación ni a márgenes agregados en API. */
export function isTrafficManager(role: AppRbacRole): boolean {
  return role === "traffic_manager";
}

type JwtMeta = {
  rbac_role?: unknown;
  role?: unknown;
  roles?: unknown;
};

function coerceAppRbacRole(raw: unknown): AppRbacRole | null {
  if (raw == null) return null;
  const s = String(raw).trim();
  if (!s) return null;
  const lower = s.toLowerCase();

  const valid: AppRbacRole[] = [
    "owner",
    "admin",
    "traffic_manager",
    "driver",
    "cliente",
    "developer",
  ];
  if (valid.includes(lower as AppRbacRole)) return lower as AppRbacRole;

  const upper = s.toUpperCase();
  const legacyUpper: Record<string, AppRbacRole> = {
    ADMIN: "owner",
    GESTOR: "traffic_manager",
    CONDUCTOR: "driver",
    OWNER: "owner",
    DRIVER: "driver",
    TRAFFIC_MANAGER: "traffic_manager",
    CLIENTE: "cliente",
    DEVELOPER: "developer",
  };
  if (legacyUpper[upper]) return legacyUpper[upper];

  if (lower === "propietario") return "owner";
  if (lower === "administrador") return "admin";

  return null;
}

/**
 * Backend FastAPI (`create_access_token` en security.py) emite en el payload:
 * - `sub` (username / identificador de sesión)
 * - `empresa_id` (opcional)
 * - `rbac_role` (opcional): owner | admin | traffic_manager | driver | cliente | developer
 * - `assigned_vehiculo_id`, `cliente_id` (opcionales)
 * Los JWT de Supabase Auth siguen usando app_metadata / user_metadata.
 */
function collectRoleCandidates(p: Record<string, unknown>): unknown[] {
  const app = p.app_metadata as JwtMeta | undefined;
  const user = p.user_metadata as JwtMeta | undefined;
  const out: unknown[] = [
    p.rbac_role,
    p.role,
    app?.rbac_role,
    app?.role,
    user?.rbac_role,
    user?.role,
  ];
  if (app?.roles != null) {
    if (Array.isArray(app.roles)) out.push(...app.roles);
    else out.push(app.roles);
  }
  return out;
}

function rbacRoleFromPayload(p: JwtPayload | null): AppRbacRole {
  if (!p) return "driver";

  const po = p as Record<string, unknown>;
  const root = coerceAppRbacRole(po.rbac_role);
  if (root) return root;

  for (const c of collectRoleCandidates(po)) {
    const r = coerceAppRbacRole(c);
    if (r) return r;
  }
  return "driver";
}

export function jwtRbacRoleFromToken(token: string | null | undefined): AppRbacRole {
  return rbacRoleFromPayload(jwtPayloadFromAccessToken(token));
}

export function jwtRbacRole(): AppRbacRole {
  return rbacRoleFromPayload(jwtPayload());
}

export function jwtSubject(): string | null {
  const sub = jwtPayload()?.sub;
  return typeof sub === "string" ? sub : null;
}

/**
 * Nombre visible: Supabase user_metadata si existe; si no, claim `email` o `sub` del JWT
 * (el backend FastAPI solo garantiza `sub` como username, p. ej. `adrian_balsa`).
 */
export function jwtDisplayName(): string {
  const p = jwtPayload();
  if (!p) return "Usuario";

  const po = p as Record<string, unknown>;
  const um = po.user_metadata as Record<string, unknown> | undefined;
  const sub =
    typeof po.sub === "string" && po.sub.trim() ? po.sub.trim() : "";

  const pick =
    (typeof um?.full_name === "string" && um.full_name.trim()) ||
    (typeof um?.name === "string" && um.name.trim()) ||
    (typeof um?.display_name === "string" && um.display_name.trim()) ||
    (typeof po.email === "string" && po.email.trim()) ||
    (typeof um?.email === "string" && um.email.trim()) ||
    sub;

  return pick || "Usuario";
}

export function jwtEmpresaId(): string | null {
  const p = jwtPayload();
  const v = p?.empresa_id ?? p?.empresaId ?? p?.tenant_id ?? p?.tenantId;
  return typeof v === "string" ? v : null;
}

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
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
  const mem = getAuthToken();
  if (mem) return mem;

  if (typeof window !== "undefined") {
    const supabase = getSupabaseClient();
    if (supabase) {
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
      if (token) return token;
    }
    return getAuthToken();
  }

  try {
    const { cookies } = await import("next/headers");
    const cookieStore = await cookies();
    const abl = cookieStore.get("abl_auth_token")?.value?.trim();
    if (abl) return abl;
  } catch {
    /* no Next / no cookies */
  }

  return null;
}

apiClient.interceptors.request.use(async (config) => {
  let token: string | null = null;
  if (typeof window !== "undefined") {
    token = await resolveAccessToken();
    if (!token) token = getAuthToken();
  } else {
    try {
      const { cookies } = await import("next/headers");
      const cookieStore = await cookies();
      const abl = cookieStore.get("abl_auth_token")?.value?.trim();
      if (abl) {
        token = abl;
      } else {
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

type AxiosConfigWith401Retry = AxiosRequestConfig & { __abl401Retry?: boolean };

apiClient.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error)) return Promise.reject(error);
    const status = error.response?.status;
    const cfg = error.config as AxiosConfigWith401Retry | undefined;
    if (!cfg || cfg.__abl401Retry || status !== 401) return Promise.reject(error);
    if (typeof window === "undefined") return Promise.reject(error);
    const path = `${cfg.baseURL ?? ""}${cfg.url ?? ""}`;
    const method = (cfg.method || "get").toUpperCase();
    if (method === "POST" && path.includes("/auth/login")) return Promise.reject(error);
    cfg.__abl401Retry = true;
    await wait(450);
    const token = await resolveAccessToken();
    cfg.headers = cfg.headers ?? {};
    const hdr = cfg.headers as Record<string, string>;
    if (token) hdr.Authorization = `Bearer ${token}`;
    else delete hdr.Authorization;
    return apiClient.request(cfg);
  },
);

export type ApiFetchOptions = RequestInit;

/** Mensaje típico de FastAPI cuando falta o no es válido el Bearer (ver `deps.get_current_user`). */
const CREDENTIALS_DETAIL_SUBSTR = "validar las credenciales";

/** True si el texto corresponde a un fallo de autenticación (401), no a un error de negocio. */
export function isAuthCredentialErrorMessage(msg: string | null | undefined): boolean {
  if (!msg || typeof msg !== "string") return false;
  const m = msg.toLowerCase();
  if (m.includes(CREDENTIALS_DETAIL_SUBSTR)) return true;
  if (/^error http 401\b/i.test(m.trim())) return true;
  return false;
}

function shouldRetry401AfterAuth(
  input: string,
  init: RequestInit,
  response: Response,
): boolean {
  if (typeof window === "undefined" || response.status !== 401) return false;
  const method = (init.method ?? "GET").toUpperCase();
  if (method === "POST" && input.includes("/auth/login")) return false;
  return true;
}

export async function apiFetch(input: string, options?: ApiFetchOptions): Promise<Response>;
export async function apiFetch<T>(
  input: string,
  options: ApiFetchOptions | undefined,
  schema: ZodSchema<T>,
): Promise<T>;
export async function apiFetch<T>(
  input: string,
  init: ApiFetchOptions = {},
  schema?: ZodSchema<T>,
): Promise<Response | T> {
  const headers = new Headers(init.headers ?? {});
  const credentials = init.credentials ?? "include";

  const token = await resolveAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response = await fetch(input, { ...init, credentials, headers });

  if (shouldRetry401AfterAuth(input, init, response)) {
    await wait(450);
    const token2 = await resolveAccessToken();
    if (token2) {
      headers.set("Authorization", `Bearer ${token2}`);
      response = await fetch(input, { ...init, credentials, headers });
    }
  }

  if (!schema) return response;
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const payload = await response.json().catch(() => null);
  const result = schema.safeParse(payload);
  if (!result.success) {
    console.error("apiFetch schema validation failed", {
      url: input,
      issues: result.error.issues,
      payload,
    });
    throw new ApiValidationError(
      `Respuesta inválida del backend para ${input}`,
      payload,
      result.error.issues,
    );
  }
  return result.data;
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

/** Certificado ESG emitido en servidor (GLEC v2.0 / ISO 14083, registro auditable). */
export async function downloadEsgCertificatePdf(
  kind: "porte" | "factura",
  subjectId: string,
): Promise<Blob> {
  const qs = new URLSearchParams({ kind });
  const res = await apiFetch(
    `${API_BASE}/api/v1/esg/certificates/${encodeURIComponent(subjectId)}/download?${qs.toString()}`,
    { credentials: "include" },
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return res.blob();
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

/**
 * LogisAdvisor (`POST /api/v1/advisor/ask`) con SSE real: chunks `data: {"text":"..."}` y cierre `{"done":true,"model":"..."}`.
 */
export async function streamAdvisorAsk(
  body: { message: string; stream?: boolean },
  handlers: {
    onDelta: (chunk: string) => void;
    onDone?: (model?: string | null) => void;
    onError?: (msg: string) => void;
  },
): Promise<void> {
  const res = await apiFetch(`${API_BASE}/api/v1/advisor/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream, application/json" },
    body: JSON.stringify({ message: body.message, stream: body.stream ?? true }),
  });
  if (!res.ok) {
    handlers.onError?.(await parseApiError(res));
    return;
  }

  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) {
    const data = (await res.json()) as { reply?: string; model?: string | null };
    if (typeof data.reply === "string") handlers.onDelta(data.reply);
    handlers.onDone?.(data.model);
    return;
  }

  if (!res.body) {
    handlers.onError?.("Respuesta vacía del servidor");
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });

      let lineEnd: number;
      while ((lineEnd = buffer.indexOf("\n")) >= 0) {
        const rawLine = buffer.slice(0, lineEnd);
        buffer = buffer.slice(lineEnd + 1);
        const line = rawLine.replace(/\r$/, "");
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6).trim();
        if (!payload) continue;
        try {
          const json = JSON.parse(payload) as {
            text?: string;
            error?: string;
            done?: boolean;
            model?: string | null;
          };
          if (json.error) {
            handlers.onError?.(json.error);
            return;
          }
          if (json.text) handlers.onDelta(json.text);
          if (json.done) handlers.onDone?.(json.model);
        } catch {
          // línea SSE malformada: ignorar
        }
      }
      if (done) break;
    }
  } finally {
    reader.releaseLock();
  }
}

export class FacturaEmailSendError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "FacturaEmailSendError";
    this.status = status;
  }
}
/** Campos usados en UI de facturas; el backend puede añadir más (VeriFactu, rectificativas). */
export type Factura = {
  id: number;
  numero_factura?: string;
  cliente_nombre?: string;
  total_factura?: number;
  estado_factura?: string;
  created_at?: string;
  tipo_factura?: string | null;
  fecha_emision?: string | null;
  is_finalized?: boolean;
  fingerprint?: string | null;
  aeat_sif_estado?: string | null;
  aeat_sif_descripcion?: string | null;
  aeat_sif_csv?: string | null;
  hash_registro?: string | null;
};

/** Alineado con `GET /api/v1/facturas/{id}/pdf-data` y `FacturaPdfTemplate`. */
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
  /** Huella resuelta para ``hc`` (SREI); misma prioridad que el backend. */
  fingerprint_hash?: string | null;
  hash_registro: string | null;
  aeat_csv_ultimo_envio: string | null;
  esg_portes_count?: number | null;
  esg_total_km?: number | null;
  esg_total_co2_kg?: number | null;
  esg_euro_iii_baseline_kg?: number | null;
  esg_ahorro_vs_euro_iii_kg?: number | null;
};

type CmrParty = {
  nombre?: string | null;
  nif?: string | null;
  direccion?: string | null;
  pais?: string | null;
};

type CmrLugarFecha = {
  lugar?: string | null;
  fecha?: string | null;
};

type CmrMercancia = {
  descripcion?: string | null;
  bultos?: number | null;
  peso_kg?: number | null;
  peso_ton?: number | null;
  volumen_m3?: number | null;
  matricula_vehiculo?: string | null;
  nombre_vehiculo?: string | null;
  nombre_conductor?: string | null;
};

export type CmrDataOut = {
  porte_id: string;
  km_estimados?: number | null;
  casilla_1_remitente: CmrParty;
  casilla_2_consignatario: CmrParty;
  casilla_3_lugar_entrega_mercancia?: string | null;
  casilla_4_lugar_fecha_toma_carga: CmrLugarFecha;
  casilla_6_12_mercancia: CmrMercancia;
  casilla_16_transportista: CmrParty;
};

export type LiveFleetVehicle = {
  id: string;
  matricula: string;
  conductor_nombre?: string | null;
  estado: string;
  ultima_latitud?: number | null;
  ultima_longitud?: number | null;
  ultima_actualizacion_gps?: string | null;
};

/** Fila de `GET /api/v1/portes/` (portes pendientes = activos en pipeline). */
export type PorteListRow = {
  id: string;
  empresa_id?: string;
  cliente_id?: string | null;
  fecha: string;
  origen: string;
  destino: string;
  km_estimados: number;
  km_vacio?: number | null;
  bultos?: number;
  descripcion?: string | null;
  precio_pactado?: number | null;
  vehiculo_id?: string | null;
  co2_emitido?: number | null;
  peso_ton?: number | null;
  estado: string;
  subcontratado?: boolean;
  factura_id?: number | null;
  lat_origin?: number | null;
  lng_origin?: number | null;
  lat_dest?: number | null;
  lng_dest?: number | null;
  real_distance_meters?: number | null;
};

/** `GET /portes/{id}` — detalle con campos ESG enriquecidos (GLEC + Euro III). */
export type PorteDetailOut = PorteListRow & {
  co2_kg?: number | null;
  vehiculo_matricula?: string | null;
  vehiculo_modelo?: string | null;
  vehiculo_normativa_euro?: string | null;
  vehiculo_engine_class?: string | null;
  vehiculo_fuel_type?: string | null;
  esg_co2_total_kg?: number | null;
  esg_co2_euro_iii_baseline_kg?: number | null;
  esg_co2_ahorro_vs_euro_iii_kg?: number | null;
};

/** Fila de `GET /flota/inventario` (normativa motor para mapa). */
export type FlotaInventarioRow = {
  id: string;
  matricula: string;
  vehiculo: string;
  normativa_euro?: string | null;
  engine_class?: string | null;
  certificacion_emisiones?: string | null;
};

const GEOCODE_CACHE_PREFIX = "abl:geocode:v1:";

/** Normaliza la dirección para clave de caché (LocalStorage). */
export function normalizeGeocodeQuery(address: string): string {
  return address.trim().replace(/\s+/g, " ").toLowerCase();
}

/** Lee coordenadas cacheadas (solo cliente). */
export function readGeocodeCache(address: string): { lat: number; lng: number } | null {
  if (typeof window === "undefined") return null;
  const k = GEOCODE_CACHE_PREFIX + normalizeGeocodeQuery(address);
  try {
    const raw = localStorage.getItem(k);
    if (!raw) return null;
    const j = JSON.parse(raw) as { lat?: unknown; lng?: unknown };
    if (typeof j.lat === "number" && typeof j.lng === "number") {
      return { lat: j.lat, lng: j.lng };
    }
  } catch {
    /* ignore corrupt cache */
  }
  return null;
}

/** Persiste coordenadas en LocalStorage (Supabase sync opcional vía edge job). */
export function writeGeocodeCache(address: string, pos: { lat: number; lng: number }): void {
  if (typeof window === "undefined") return;
  const k = GEOCODE_CACHE_PREFIX + normalizeGeocodeQuery(address);
  try {
    localStorage.setItem(k, JSON.stringify(pos));
  } catch {
    /* quota / private mode */
  }
}

/**
 * Geocodifica con `google.maps.Geocoder`, usando caché local para reducir coste.
 * Debe ejecutarse en el cliente con Maps JS ya cargado.
 */
export async function geocodeAddressWithCache(
  geocoder: google.maps.Geocoder,
  address: string,
): Promise<{ lat: number; lng: number } | null> {
  const q = normalizeGeocodeQuery(address);
  if (!q) return null;
  const cached = readGeocodeCache(q);
  if (cached) return cached;
  return new Promise((resolve) => {
    geocoder.geocode({ address: q }, (results, status) => {
      if (status === "OK" && results?.[0]?.geometry?.location) {
        const loc = results[0].geometry.location;
        const pos = { lat: loc.lat(), lng: loc.lng() };
        writeGeocodeCache(q, pos);
        resolve(pos);
      } else {
        resolve(null);
      }
    });
  });
}

export type SimulationInput = {
  cambio_combustible_pct: number;
  cambio_salarios_pct: number;
  cambio_peajes_pct: number;
};

export type SimulationResult = {
  ebitda_base_eur: number;
  ebitda_simulado_eur: number;
  impacto_mensual_estimado_eur: number;
  impacto_ebitda_eur: number;
  impacto_ebitda_pct: number;
  break_even: { tarifa_incremento_pct: number };
  periodo_meses: number;
};

export type CIPMatrixPoint = {
  ruta: string;
  margen_neto: number;
  emisiones_co2: number;
  total_portes: number;
};

/** `GET /api/v1/bi/dashboard/summary` */
export type BiDashboardSummary = {
  dso_days: number | null;
  dso_sample_size: number;
  avg_margin_eur: number | null;
  avg_margin_portes: number;
  total_co2_saved_kg: number | null;
  co2_saved_portes: number;
  avg_efficiency_eur_per_eur_km: number | null;
  efficiency_sample_size: number;
};

/** Punto `GET /api/v1/bi/charts/profitability` (Recharts: km vs margin_eur). */
export type BiProfitabilityPoint = {
  porte_id: string;
  km: number;
  /** Margen P&L: precio − combustible imputado − opex no combustible/km (o proxy km×coste). */
  margin_eur: number;
  margin_estimado_legacy_eur?: number | null;
  /** True si no hay ticket de combustible vinculado a vehículo/fecha. */
  estimated_margin?: boolean;
  allocated_fuel_eur?: number | null;
  other_opex_eur?: number | null;
  precio_pactado?: number | null;
  estado?: string | null;
  cliente?: string | null;
  vehiculo?: string | null;
  route_label?: string | null;
};

export type BiProfitabilityCharts = {
  points: BiProfitabilityPoint[];
  coste_operativo_eur_km: number;
};

export type BiTreemapNode = {
  name: string;
  size: number;
  margen_estimado?: number | null;
  porte_id?: string | null;
  estimated_fallback?: boolean;
};

export type BiHeatmapCell = {
  x_bin: string;
  y_bin: string;
  count: number;
  total_co2_kg: number;
};

export type BiEsgImpactCharts = {
  matrix: unknown[];
  heatmap_cells: BiHeatmapCell[];
  treemap_nodes: BiTreemapNode[];
  meta?: Record<string, unknown>;
};

export type VerifactuChainAudit = {
  is_valid: boolean;
  total_verified: number;
  factura_id?: number | null;
  ejercicio?: number | null;
  error?: string | null;
};

/** Fila de `GET /api/v1/audit-logs` (acciones pueden incluir valores distintos de INSERT/UPDATE/DELETE). */
export type AuditLogRow = {
  id: string;
  empresa_id: string;
  /** Tabla afectada (alias legacy posible: `tabla_origen`). */
  table_name: string;
  tabla_origen?: string;
  record_id: string;
  action: string;
  old_data?: Record<string, unknown> | null;
  new_data?: Record<string, unknown> | null;
  changed_by?: string | null;
  created_at: string;
};

export const fetchAuditLogs = async (limit = 10) =>
  getJson<AuditLogRow[]>(`${API_BASE}/api/v1/audit-logs?limit=${encodeURIComponent(String(limit))}`);

export type VerifactuQrPreview = {
  found: boolean;
  qr_png_base64?: string | null;
  numero_factura?: string | null;
  fingerprint_hash?: string | null;
  aeat_url?: string | null;
};
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

export type ClienteOperationalEstadoUi = "activo" | "inactivo" | "riesgo";

export type ClienteOperationalDetail = {
  cliente: {
    id: string;
    nombre: string;
    email?: string | null;
    limite_credito?: number;
    riesgo_aceptado?: boolean;
    mandato_activo?: boolean;
    is_blocked?: boolean;
    estado_ui: ClienteOperationalEstadoUi;
  };
  metricas: {
    total_facturado: number;
    portes_realizados: number;
    dias_pago_promedio: number | null;
  };
  facturacion_mensual: Array<{ mes: string; total_facturado: number }>;
  portes_recientes: Array<{
    id: string;
    origen: string;
    destino: string;
    fecha: string | null;
    estado: string;
    fecha_entrega_real: string | null;
  }>;
};

export const fetchClienteOperationalDetail = async (clienteId: string) =>
  getJson<ClienteOperationalDetail>(
    `${API_BASE}/api/v1/clientes/${encodeURIComponent(clienteId)}/detail`,
  );
export type PortalFacturaRow = {
  id: string | number;
  numero_factura: string;
  fecha_emision?: string | null;
  total_factura: number;
  estado_pago: string;
};

export type PortalPorteRow = {
  id: string | number;
  origen: string;
  destino: string;
  fecha_entrega: string | null;
};

export type FuelImportacionResponse = {
  errores: string[];
  importedAt?: string;
  total_litros: number;
  total_euros: number;
  total_co2_kg: number;
  filas_importadas_ok: number;
  total_filas_leidas: number;
};
export type MantenimientoUrgencia = "CRITICO" | "ADVERTENCIA" | "OK";
export type MantenimientoAlertaKm = {
  urgencia: MantenimientoUrgencia;
  plan_id: string;
  tipo_tarea: string;
  vehiculo_id: string;
  matricula?: string | null;
  /** Nombre legible del vehículo (inventario), si el backend lo envía */
  vehiculo?: string | null;
  intervalo_km: number;
  km_desde_ultimo: number;
  desgaste: number;
  ultimo_km_realizado?: number;
  odometro_actual?: number;
};
export type MantenimientoAlertaAdmin = {
  urgencia: MantenimientoUrgencia;
  vehiculo_id: string;
  tipo_tramite: string;
  fecha_vencimiento: string;
  dias_restantes: number;
  matricula?: string | null;
  vehiculo?: string | null;
};
export type MantenimientoAlerta = MantenimientoAlertaKm | MantenimientoAlertaAdmin;

export type MovimientoSugeridoConciliacion = {
  movimiento_id: string;
  fecha: string;
  importe: number;
  concepto?: string | null;
  iban_origen?: string | null;
  confidence_score?: number | null;
  factura_numero?: string | null;
  cliente_nombre?: string | null;
  factura_total?: number | null;
  factura_fecha?: string | null;
  razonamiento_ia?: string | null;
};
export type ExportContableTipo = string;
export type CreditAlert = {
  cliente_id: string;
  nombre_cliente: string;
  nivel_alerta: "CRITICAL" | "WARNING" | string;
  saldo_pendiente: number;
  limite_credito: number;
  porcentaje_consumo: number;
};

export type FinanceEsgReport = {
  periodo: string;
  total_co2_kg: number;
  total_portes: number;
};

export type RiskRankingRow = {
  cliente_id: string;
  nombre: string;
  saldo_pendiente: number;
  riesgo_score: number;
  valor_riesgo: number;
  mandato_sepa_activo: boolean;
};

export type RouteMarginRow = {
  ruta: string;
  total_portes: number;
  ingresos_totales: number;
  costes_totales: number;
  margen_neto: number;
  margen_porcentual: number;
};
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
export type AdvancedMetricsMonthRow = {
  periodo: string;
  ingresos_facturacion_eur: number;
  gastos_operativos_eur: number;
  coste_por_km_eur: number | null;
  emisiones_co2_kg: number;
};

export type AdvancedMetricsResponse = {
  meses: AdvancedMetricsMonthRow[];
  generado_en?: string;
  nota_metodologia?: string | null;
  /** % diferencia margen P&L real vs estimado (últimos 6 meses, portes completados). */
  real_margin_index?: number | null;
  /** Ingresos porte / € combustible real imputado. */
  fuel_efficiency_ratio?: number | null;
};

/** Listado/creación webhooks: el backend expone campos distintos según flujo (B2B vs panel desarrolladores). */
export type WebhookB2BRow = {
  id: string;
  secret_key?: string;
  /** Flujo integraciones (`/settings/integrations`) */
  target_url?: string;
  event_type?: string;
  /** Flujo desarrolladores (`/dashboard/configuracion/desarrolladores`) */
  url?: string;
  event_types?: string[];
  is_active?: boolean;
  created_at?: string;
};

/** Alias histórico; mismo shape que un endpoint listado. */
export type WebhookEndpoint = WebhookB2BRow;
export type WebhookEventType = string;

export const WEBHOOK_EVENT_TYPES: WebhookEventType[] = [
  "credit.limit_exceeded",
  "invoice.created",
  "invoice.paid",
  "invoice.overdue",
];

async function getJson<T = unknown>(url: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(url, init);
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as T;
}

export const refreshAccessToken = async () =>
  getJson<{ access_token?: string }>(`${API_BASE}/auth/refresh`, { method: "POST", credentials: "include" });
export const fetchPortalFacturas = async () => getJson<PortalFacturaRow[]>(`${API_BASE}/api/v1/portal/facturas`);
export const fetchPortalPortes = async () => getJson<PortalPorteRow[]>(`${API_BASE}/api/v1/portal/portes`);

/** Respuesta onboarding portal (riesgo / límite); alineado con `RiskAssessmentCard` / onboarding. */
export type PortalOnboardingMyRisk = {
  score: number;
  creditLimitEur: number;
  collectionTerms: string;
  reasons: string[];
};

export type OnboardingSetupInput = {
  company_name: string;
  cif: string;
  address: string;
  initial_fleet_type: string;
  target_margin_pct?: number | null;
};

export type OnboardingSetupResponse = {
  empresa_id: string;
  profile_id: string;
  role: string;
};

export const fetchPortalMyRisk = async () =>
  getJson<PortalOnboardingMyRisk>(`${API_BASE}/api/v1/portal/onboarding/my-risk`);

export const postPortalAcceptRisk = async (payload: Record<string, unknown> = {}) =>
  getJson<unknown>(`${API_BASE}/api/v1/portal/onboarding/accept-risk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const postAuthOnboardingSetup = async (payload: OnboardingSetupInput) =>
  getJson<OnboardingSetupResponse>(`${API_BASE}/auth/onboarding/setup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export type PortalMandateSetupResponse = {
  has_active_mandate?: boolean;
  redirect_url?: string;
};

export const postPortalSetupMandate = async () =>
  getJson<PortalMandateSetupResponse>(`${API_BASE}/api/v1/payments/gocardless/mandates/setup`, { method: "POST" });
export const portalFacturaPdfUrl = (id: string | number) => `${API_BASE}/api/v1/portal/facturas/${id}/pdf`;
export const portalAlbaranPdfUrl = (id: string | number) => `${API_BASE}/api/v1/portal/portes/${id}/albaran-pdf`;
export const getFacturaPdfData = async (id: string | number) =>
  getJson<FacturaPdfData>(`${API_BASE}/api/v1/facturas/${id}/pdf-data`);
export const getPorteCmrData = async (id: string | number) => getJson<CmrDataOut>(`${API_BASE}/api/v1/portes/${id}/cmr`);
export const getPorteDetail = async (id: string | number) =>
  getJson<PorteDetailOut>(`${API_BASE}/portes/${encodeURIComponent(String(id))}`);
export const getLiveFleetTracking = async () =>
  getJson<LiveFleetVehicle[]>(`${API_BASE}/api/v1/flota/live-tracking`);
export const postFirmaEntrega = async (
  idOrPayload: string | Record<string, unknown>,
  maybePayload?: Record<string, unknown>,
) => {
  const payload = typeof idOrPayload === "string" ? { id: idOrPayload, ...(maybePayload ?? {}) } : idOrPayload;
  return getJson<unknown>(`${API_BASE}/api/v1/portes/firma-entrega`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
};
export const getSugerenciasPendientes = async () =>
  getJson<MovimientoSugeridoConciliacion[]>(`${API_BASE}/api/v1/banking/reconciliation/suggestions`);
export type ConciliarAiResponse = {
  sugerencias_guardadas: number;
};

export const postConciliarAi = async (payload: Record<string, unknown> = {}) =>
  getJson<ConciliarAiResponse>(`${API_BASE}/api/v1/banking/reconciliation/ai`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const postConfirmarSugerencia = async (
  payloadOrId: Record<string, unknown> | string,
  aprobar?: boolean,
) => {
  const payload =
    typeof payloadOrId === "string"
      ? { movimiento_id: payloadOrId, aprobar: Boolean(aprobar) }
      : payloadOrId;
  return getJson<unknown>(`${API_BASE}/api/v1/banking/reconciliation/suggestions/confirm`, {
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
  "plan_id" in row && typeof row.plan_id === "string";
export type RegistrarMantenimientoResponse = {
  ultimo_km_realizado: number;
  gasto_id: string | number;
};

export const postRegistrarMantenimiento = async (payload: Record<string, unknown>) =>
  getJson<RegistrarMantenimientoResponse>(`${API_BASE}/api/v1/flota/mantenimiento/registrar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
export const getAdvancedMetrics = async () =>
  getJson<AdvancedMetricsResponse>(`${API_BASE}/api/v1/dashboard/advanced-metrics`);
export const listWebhooksB2B = async () => getJson<WebhookB2BRow[]>(`${API_BASE}/api/v1/webhooks/`);
export const createWebhookB2B = async (payload: Record<string, unknown>) =>
  getJson<WebhookB2BRow>(`${API_BASE}/api/v1/webhooks/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
export const deleteWebhookB2B = async (id: string) =>
  getJson<unknown>(`${API_BASE}/api/v1/webhooks/${encodeURIComponent(id)}`, { method: "DELETE" });
export const revealWebhookSecret = async (id: string) =>
  getJson<{ secret_key: string }>(`${API_BASE}/api/v1/webhooks/${encodeURIComponent(id)}/secret`);
export const testWebhookB2B = async (id: string) =>
  getJson<unknown>(`${API_BASE}/api/v1/webhooks/${encodeURIComponent(id)}/test`, { method: "POST" });

export type FacturaEmailSendResponse = {
  destinatario: string;
};

export const api = Object.assign(apiClient, {
  portes: {
    /** Portes pendientes (activos en pipeline). */
    list: () => getJson<PorteListRow[]>(`${API_BASE}/api/v1/portes/`),
    get: (id: string | number) => getPorteDetail(id),
  },
  flota: {
    inventario: () => getJson<FlotaInventarioRow[]>(`${API_BASE}/flota/inventario`),
  },
  facturas: {
    get: (facturaId: number) => getJson<Factura>(`${API_BASE}/facturas/${encodeURIComponent(String(facturaId))}`),
    getAll: () => getJson<Factura[]>(`${API_BASE}/facturas`),
    sendByEmail: async (facturaId: number) => {
      const res = await apiFetch(`${API_BASE}/facturas/${facturaId}/send-email`, { method: "POST" });
      if (!res.ok) {
        throw new FacturaEmailSendError(await parseApiError(res), res.status);
      }
      return (await res.json()) as FacturaEmailSendResponse;
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
  bi: {
    /** ``from`` / ``to``: YYYY-MM-DD (inclusive). Query params ``from`` y ``to`` en la API. */
    summary: (from: string, to: string) =>
      getJson<BiDashboardSummary>(
        `${API_BASE}/api/v1/bi/dashboard/summary?${new URLSearchParams({ from, to }).toString()}`,
      ),
    profitability: (from: string, to: string) =>
      getJson<BiProfitabilityCharts>(
        `${API_BASE}/api/v1/bi/charts/profitability?${new URLSearchParams({ from, to }).toString()}`,
      ),
    esgImpact: (from: string, to: string) =>
      getJson<BiEsgImpactCharts>(
        `${API_BASE}/api/v1/bi/charts/esg-impact?${new URLSearchParams({ from, to }).toString()}`,
      ),
  },
  clientes: {
    resendInvite: (clienteId: string) =>
      getJson<unknown>(`${API_BASE}/api/v1/clientes/${encodeURIComponent(clienteId)}/resend-invite`, {
        method: "POST",
      }),
    fetchOperationalDetail: (clienteId: string) => fetchClienteOperationalDetail(clienteId),
  },
  webhooks: {
    getEndpoints: () => listWebhooksB2B(),
    createEndpoint: (payload: Record<string, unknown>) => createWebhookB2B(payload),
    deleteEndpoint: (id: string) => deleteWebhookB2B(id),
    getEndpointSecret: async (id: string) => {
      const out = await revealWebhookSecret(id);
      return { secret_key: out.secret_key };
    },
  },
  verifactu: {
    verifyChain: (ejercicio?: number) =>
      getJson<VerifactuChainAudit>(
        `${API_BASE}/api/v1/verifactu/audit/verify-chain${ejercicio != null ? `?ejercicio=${ejercicio}` : ""}`,
      ),
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
      const res = await apiFetch(`${API_BASE}/api/v1/finance/esg-report/download`, { credentials: "include" });
      if (!res.ok) throw new Error(await parseApiError(res));
      return res.blob();
    },
  },
});
export { apiClient };
export default apiClient;
