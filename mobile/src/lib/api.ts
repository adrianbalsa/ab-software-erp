import { getApiBaseUrl } from "./config";

/** Token en memoria para cabeceras; se sincroniza con SecureStore desde AuthContext. */
let memoryAccessToken: string | null = null;

export function setMemoryAccessToken(token: string | null): void {
  memoryAccessToken = token;
}

export function getMemoryAccessToken(): string | null {
  return memoryAccessToken;
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

type FetchJsonOptions = RequestInit & {
  /** Si es false, no envía Authorization (p. ej. login). Por defecto true. */
  auth?: boolean;
};

export async function apiFetchJson<T>(
  path: string,
  options: FetchJsonOptions = {},
): Promise<T> {
  const { auth = true, headers: initHeaders, ...rest } = options;
  const base = getApiBaseUrl();
  const url = path.startsWith("http") ? path : `${base}${path.startsWith("/") ? path : `/${path}`}`;

  const headers = new Headers(initHeaders);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");

  if (auth) {
    const t = memoryAccessToken;
    if (t) headers.set("Authorization", `Bearer ${t}`);
  }

  const res = await fetch(url, { ...rest, headers });
  const text = await res.text();
  let data: unknown = text;
  if (text) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? (data as { detail: unknown }).detail
        : data;
    throw new ApiError(`HTTP ${res.status}`, res.status, detail);
  }

  return data as T;
}

/** Liveness barato del backend (sin JWT). */
export async function fetchLiveProbe(): Promise<{ ok: boolean; status: number; snippet: string }> {
  const base = getApiBaseUrl();
  try {
    const res = await fetch(`${base}/live`, { method: "GET" });
    const text = (await res.text()).slice(0, 200);
    return { ok: res.ok, status: res.status, snippet: text };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, status: 0, snippet: msg };
  }
}
