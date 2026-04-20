import { API_BASE, apiFetch } from "@/lib/api";

/** Valor build-time opcional (primera pinta sin sesión / sin fetch). */
export function publicOperationalCostEurKmDefault(): number {
  const raw = process.env.NEXT_PUBLIC_COSTE_OPERATIVO_EUR_KM;
  if (raw == null || raw === "") return 0.62;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 0.62;
}

let _memo: number | null = null;
let _inflight: Promise<number> | null = null;

/**
 * Coste €/km activo en backend (misma fuente que mapas / BI).
 * Cache en memoria de pestaña tras la primera respuesta OK.
 */
export async function getOperationalCostEurKmCached(): Promise<number> {
  if (_memo != null) return _memo;
  if (_inflight) return _inflight;
  _inflight = (async () => {
    try {
      const res = await apiFetch(`${API_BASE}/api/v1/config/operational-pricing`, { credentials: "include" });
      if (res.ok) {
        const j = (await res.json()) as { coste_operativo_eur_km?: unknown };
        const v = Number(j.coste_operativo_eur_km);
        if (Number.isFinite(v) && v > 0) return v;
      }
    } catch {
      /* ignore */
    }
    return publicOperationalCostEurKmDefault();
  })();
  try {
    const v = await _inflight;
    _memo = v;
    return v;
  } finally {
    _inflight = null;
  }
}
