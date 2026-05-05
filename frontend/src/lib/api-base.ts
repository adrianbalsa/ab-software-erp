/** Resolución de URL base de la API (browser vs SSR en Docker). */

const DEFAULT_FALLBACK = "https://api.ablogistics-os.com";

const FETCH_FAILURE_HINT =
  "No se pudo conectar con el servidor. Comprueba tu red, bloqueadores o que la API esté disponible.";

/** Orígenes locales (no forzar HTTPS). */
function isLocalApiHost(raw: string): boolean {
  const s = raw.trim();
  try {
    const u = new URL(s.includes("://") ? s : `https://${s}`);
    const h = u.hostname.toLowerCase();
    return h === "localhost" || h === "127.0.0.1";
  } catch {
    return /^https?:\/\/(localhost|127\.0\.0\.1)\b/i.test(s);
  }
}

/**
 * En servidor o env mal configurado: evita `http://api....` hacia producción (SSR/login).
 * No toca `http://localhost` / 127.0.0.1.
 */
function normalizeApiBaseUrl(raw: string): string {
  let s = raw.trim().replace(/\/$/, "");
  if (!s) return DEFAULT_FALLBACK;
  if (!/^https?:\/\//i.test(s)) {
    s = `https://${s}`;
  }
  if (!isLocalApiHost(s) && /^http:\/\//i.test(s)) {
    return `https://${s.slice("http://".length)}`;
  }
  return s;
}

/** Evita mixed-content: página HTTPS + API `http://` → el navegador bloquea silenciosamente el fetch. */
function coerceHttpsWhenPageIsSecure(raw: string): string {
  let s = raw.trim().replace(/\/$/, "");
  if (!s) return s;
  if (!/^https?:\/\//i.test(s)) {
    s = `https://${s}`;
  }
  if (typeof window !== "undefined" && window.location.protocol === "https:" && /^http:\/\//i.test(s)) {
    return `https://${s.slice("http://".length)}`;
  }
  return s;
}

/** Errores típicos del navegador ante CORS, TLS o host caído (antes de respuesta HTTP). */
export function isLikelyNetworkFetchError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  if (err.name === "AbortError") return false;
  const m = err.message.toLowerCase();
  return (
    m.includes("failed to fetch") ||
    m.includes("networkerror") ||
    m.includes("network request failed") ||
    m.includes("load failed") ||
    (err.name === "TypeError" && (m.includes("fetch") || m === "failed to fetch"))
  );
}

export function userFacingFetchFailureMessage(err: unknown): string {
  if (isLikelyNetworkFetchError(err)) return FETCH_FAILURE_HINT;
  if (err instanceof Error && err.message.trim()) return err.message.trim();
  return FETCH_FAILURE_HINT;
}

export function getPublicApiBase(): string {
  return (
    process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_BASE?.trim() ||
    ""
  );
}

/** Base URL para fetch: en servidor usa INTERNAL_API_BASE_URL si existe (red Docker). */
export function resolveApiBase(): string {
  const pub = coerceHttpsWhenPageIsSecure(getPublicApiBase());
  if (typeof window === "undefined") {
    const internal = process.env.INTERNAL_API_BASE_URL?.trim().replace(/\/$/, "");
    if (internal) return normalizeApiBaseUrl(internal);
    if (pub) return normalizeApiBaseUrl(pub);
    return normalizeApiBaseUrl(DEFAULT_FALLBACK);
  }
  if (pub) return normalizeApiBaseUrl(pub);
  return normalizeApiBaseUrl(DEFAULT_FALLBACK);
}
