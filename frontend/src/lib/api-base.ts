/** Resolución de URL base de la API (browser vs SSR en Docker). */

const DEFAULT_FALLBACK = "https://api.ablogistics-os.com";

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
    if (internal) return internal;
    if (pub) return pub;
    return DEFAULT_FALLBACK;
  }
  if (pub) return pub;
  return DEFAULT_FALLBACK;
}
