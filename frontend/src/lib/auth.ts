/**
 * Persistencia de sesión (JWT) y cabeceras para la API.
 * Clave canónica: `abl_auth_token` (migración automática desde `jwt_token` legacy).
 */

export const AUTH_TOKEN_KEY = "abl_auth_token";

const LEGACY_JWT_KEY = "jwt_token";

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const current = localStorage.getItem(AUTH_TOKEN_KEY);
    if (current) return current;
    const legacy = localStorage.getItem(LEGACY_JWT_KEY);
    if (legacy) {
      localStorage.setItem(AUTH_TOKEN_KEY, legacy);
      localStorage.removeItem(LEGACY_JWT_KEY);
      return legacy;
    }
    return null;
  } catch {
    return null;
  }
}

export function setAuthToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(AUTH_TOKEN_KEY, token.trim());
    localStorage.removeItem(LEGACY_JWT_KEY);
  } catch {
    /* ignore */
  }
}

export function clearAuthToken(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(LEGACY_JWT_KEY);
  } catch {
    /* ignore */
  }
}

/** Mismo nombre que `ABL_JWT_UPDATED_EVENT` en api.ts (evita import circular auth ↔ api). */
const JWT_UPDATED_EVENT = "abl:jwt-updated";

/**
 * Cierra sesión: borra JWT, notifica a hooks (`useRole`, etc.) y navega.
 * Por defecto recarga la raíz del mismo origen (login en `app.*`, landing en dominio marketing).
 * Anula con `NEXT_PUBLIC_POST_LOGOUT_URL` (p. ej. `https://ablogistics-os.com`).
 */
export function logout(): void {
  clearAuthToken();
  if (typeof window === "undefined") return;
  try {
    window.dispatchEvent(new CustomEvent(JWT_UPDATED_EVENT));
  } catch {
    /* ignore */
  }
  const override =
    typeof process !== "undefined" ? process.env.NEXT_PUBLIC_POST_LOGOUT_URL?.trim() : "";
  if (override) {
    window.location.assign(override);
    return;
  }
  window.location.assign("/");
}

/** Cabeceras para `fetch` al backend (Bearer). */
export function authHeaders(): Record<string, string> {
  const t = getAuthToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}
