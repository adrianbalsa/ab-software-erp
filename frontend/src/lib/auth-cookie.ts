/**
 * Cookie HttpOnly `abl_auth_token` (misma firma que el backend; el frontend no valida la firma con secreto).
 * Opciones alineadas entre login (server action) y logout (route handler).
 *
 * Env (Vercel / local):
 * - AUTH_COOKIE_DOMAIN: p.ej. `.ablogistics-os.com` (punto inicial = subdominios). Omitir en localhost.
 * - AUTH_COOKIE_SAME_SITE: `lax` | `strict` | `none` (none exige HTTPS + secure).
 * - AUTH_COOKIE_SECURE: `true` | `false` (por defecto true en production o si sameSite=none).
 */

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
