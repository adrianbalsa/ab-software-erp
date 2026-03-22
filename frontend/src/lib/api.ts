/** URL del backend. Prioridad: API_URL → API_BASE_URL → API_BASE → localhost. */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "http://localhost:8000";

/** Authorization desde `localStorage` (misma sesión que el resto del front). */
export function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    const t = localStorage.getItem("jwt_token");
    return t ? { Authorization: `Bearer ${t}` } : {};
  } catch {
    return {};
  }
}

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
    const t = localStorage.getItem("jwt_token");
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
        localStorage.setItem("jwt_token", t);
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
