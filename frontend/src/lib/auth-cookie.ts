/**
 * Cookie HttpOnly `abl_auth_token` (misma firma que el backend; el frontend no valida la firma con secreto).
 * Opciones alineadas entre login (server action) y logout (route handler).
 *
 * El backend exige `Authorization: Bearer <jwt>`. La cookie HttpOnly no es legible en JS;
 * el token duplicado en `localStorage` (`abl_auth_token`, ver `@/lib/auth`) es lo que usa
 * el cliente para rellenar Bearer. Para SSR, leer la cookie con `cookies()` en `server-api` / `apiFetch`.
 *
 * Env (Vercel / local):
 * - AUTH_COOKIE_DOMAIN: p.ej. `.ablogistics-os.com` (punto inicial = subdominios). Omitir en localhost.
 * - AUTH_COOKIE_SAME_SITE: `lax` | `strict` | `none` (none exige HTTPS + secure).
 * - AUTH_COOKIE_SECURE: `true` | `false` (por defecto true en production o si sameSite=none).
 */

import { getAuthToken as getAuthTokenFromStore } from "@/lib/auth";

/** Nombre de la cookie HttpOnly paralela al JWT en localStorage. */
export const ABL_AUTH_COOKIE_NAME = "abl_auth_token" as const;

/**
 * JWT en el navegador para cabeceras `Authorization` (misma sesión que {@link ABL_AUTH_COOKIE_NAME}).
 * HttpOnly impide leer la cookie aquí; se usa el valor sincronizado en localStorage al iniciar sesión.
 */
export function getAccessTokenForApiRequest(): string | null {
  if (typeof window === "undefined") return null;
  return getAuthTokenFromStore();
}

export type AuthCookieSetOptions = {
  path: string;
  httpOnly: boolean;
  secure: boolean;
  sameSite: "lax" | "strict" | "none";
  maxAge: number;
  domain?: string;
};

export function getAblAuthCookieSetOptions(): AuthCookieSetOptions {
  const domainRaw = process.env.AUTH_COOKIE_DOMAIN?.trim();
  const domain = domainRaw || undefined;

  const raw = (process.env.AUTH_COOKIE_SAME_SITE || "lax").toLowerCase();
  const sameSite: "lax" | "strict" | "none" =
    raw === "none" || raw === "strict" || raw === "lax" ? raw : "lax";

  const explicitSecure = process.env.AUTH_COOKIE_SECURE?.trim().toLowerCase();
  const secure =
    explicitSecure === "false"
      ? false
      : explicitSecure === "true" || sameSite === "none" || process.env.NODE_ENV === "production";

  return {
    path: "/",
    httpOnly: true,
    secure,
    sameSite,
    maxAge: 60 * 60 * 24 * 7,
    ...(domain ? { domain } : {}),
  };
}

/** Opciones para borrar la cookie (mismas path/domain que al setear). */
export function getAblAuthCookieDeleteOptions(): Pick<
  AuthCookieSetOptions,
  "path" | "domain" | "secure" | "sameSite"
> {
  const o = getAblAuthCookieSetOptions();
  return {
    path: o.path,
    secure: o.secure,
    sameSite: o.sameSite,
    ...(o.domain ? { domain: o.domain } : {}),
  };
}
