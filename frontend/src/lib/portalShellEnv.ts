import { API_BASE } from "@/lib/api";

/** Muestra host de API en el shell del portal solo en dev o API local (no en producción típica). */
export function isPortalApiBaseDebugVisible(): boolean {
  if (process.env.NODE_ENV === "development") return true;
  try {
    const h = new URL(API_BASE).hostname;
    return h === "localhost" || h === "127.0.0.1";
  } catch {
    return false;
  }
}

export function portalSupportMailto(): string {
  const addr = (process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "comercial@ablogistics.os").trim();
  const subject = encodeURIComponent("Portal cliente · soporte");
  return `mailto:${addr}?subject=${subject}`;
}
