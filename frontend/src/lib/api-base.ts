/** Resolución de URL base de la API (browser vs SSR en Docker). */

const DEFAULT_FALLBACK = "https://api.ablogistics-os.com";

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
  const pub = getPublicApiBase().replace(/\/$/, "");
  if (typeof window === "undefined") {
    const internal = process.env.INTERNAL_API_BASE_URL?.trim().replace(/\/$/, "");
    if (internal) return internal;
    if (pub) return pub;
    return DEFAULT_FALLBACK;
  }
  if (pub) return pub;
  return DEFAULT_FALLBACK;
}
