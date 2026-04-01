"use client";

import { useCallback, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  Calculator,
  CircleDollarSign,
  Loader2,
  MapPin,
  Route,
  Timer,
} from "lucide-react";

import { API_BASE, apiFetch, parseApiError } from "@/lib/api";

export type CotizadorInteligenteProps = {
  empresaId: string;
};

type CotizarApiResponse = {
  kilometros_totales: number;
  tiempo_estimado_min: number;
  coste_operativo_estimado: number;
  margen_proyectado: number;
  es_rentable: boolean | null;
};

function formatEta(minutes: number): string {
  const m = Math.max(0, Math.round(minutes));
  if (m === 0) return "—";
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  if (rest === 0) return `${h} h`;
  return `${h} h ${rest} min`;
}

function formatEur(n: number): string {
  return new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

export function CotizadorInteligente({ empresaId }: CotizadorInteligenteProps) {
  const [origen, setOrigen] = useState("");
  const [destino, setDestino] = useState("");
  const [precioOferta, setPrecioOferta] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CotizarApiResponse | null>(null);

  const precioNum = useMemo(() => {
    const n = parseFloat(precioOferta.replace(",", "."));
    return Number.isFinite(n) ? n : NaN;
  }, [precioOferta]);

  const margenSobreOferta = useMemo(() => {
    if (!result || !Number.isFinite(precioNum)) return null;
    return precioNum - result.coste_operativo_estimado;
  }, [precioNum, result]);

  const onSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      setResult(null);

      const o = origen.trim();
      const d = destino.trim();
      if (!o || !d) {
        setError("Indica origen y destino.");
        return;
      }

      setLoading(true);
      try {
        const payload = {
          origen: o,
          destino: d,
          empresa_id: empresaId,
          precio_oferta: Number.isFinite(precioNum) ? precioNum : 0,
        };
        const res = await apiFetch(`${API_BASE.replace(/\/$/, "")}/api/v1/portes/cotizar`, {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          setError(await parseApiError(res));
          return;
        }
        const data = (await res.json()) as CotizarApiResponse;
        setResult(data);
      } catch {
        setError("No se pudo contactar con el servidor.");
      } finally {
        setLoading(false);
      }
    },
    [destino, empresaId, origen, precioNum],
  );

  return (
    <section className="rounded-3xl border border-zinc-800/90 bg-zinc-900/50 p-6 shadow-xl shadow-black/25 backdrop-blur-sm sm:p-8">
      <div className="mb-6 flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
          <Calculator className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-white sm:text-xl">
            Cotizador inteligente
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-zinc-400">
            Valida distancia, tiempo y viabilidad económica con el margen operativo de tu empresa antes de
            registrar el porte.
          </p>
        </div>
      </div>

      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block space-y-2">
            <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-zinc-500">
              <MapPin className="h-3.5 w-3.5 text-emerald-500/80" />
              Origen
            </span>
            <input
              type="text"
              value={origen}
              onChange={(e) => setOrigen(e.target.value)}
              placeholder="Ciudad, polígono o dirección"
              className="w-full rounded-2xl border border-zinc-700/80 bg-zinc-950/60 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 outline-none ring-emerald-500/30 transition focus:border-emerald-500/50 focus:ring-2"
              autoComplete="off"
            />
          </label>
          <label className="block space-y-2">
            <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-zinc-500">
              <MapPin className="h-3.5 w-3.5 text-sky-500/80" />
              Destino
            </span>
            <input
              type="text"
              value={destino}
              onChange={(e) => setDestino(e.target.value)}
              placeholder="Ciudad, polígono o dirección"
              className="w-full rounded-2xl border border-zinc-700/80 bg-zinc-950/60 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 outline-none ring-emerald-500/30 transition focus:border-emerald-500/50 focus:ring-2"
              autoComplete="off"
            />
          </label>
        </div>

        <label className="block space-y-2">
          <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-zinc-500">
            <CircleDollarSign className="h-3.5 w-3.5 text-amber-400/90" />
            Precio oferta (EUR)
          </span>
          <input
            type="text"
            inputMode="decimal"
            value={precioOferta}
            onChange={(e) => setPrecioOferta(e.target.value)}
            placeholder="Ej. 1250"
            className="w-full max-w-md rounded-2xl border border-zinc-700/80 bg-zinc-950/60 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 outline-none ring-emerald-500/30 transition focus:border-emerald-500/50 focus:ring-2"
          />
        </label>

        {error && (
          <div className="flex items-start gap-2 rounded-2xl border border-red-500/40 bg-red-950/35 px-4 py-3 text-sm text-red-200">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-emerald-600 to-emerald-500 px-6 py-3.5 text-sm font-semibold text-zinc-950 shadow-lg shadow-emerald-500/20 transition hover:from-emerald-500 hover:to-emerald-400 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Calculando…
            </>
          ) : (
            <>
              Cotizar ruta
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>
      </form>

      {result && (
        <div className="mt-8 rounded-3xl border border-zinc-800/80 bg-zinc-950/40 p-5 sm:p-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Resultado</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-zinc-800/80 bg-zinc-900/40 p-4">
              <div className="flex items-center gap-2 text-zinc-500">
                <Route className="h-4 w-4 text-zinc-400" />
                <span className="text-xs font-medium uppercase tracking-wide">Kilómetros totales</span>
              </div>
              <p className="mt-2 text-2xl font-bold tabular-nums text-white">{result.kilometros_totales}</p>
              <p className="text-xs text-zinc-500">Ruta carretera (Google Maps)</p>
            </div>
            <div className="rounded-2xl border border-zinc-800/80 bg-zinc-900/40 p-4">
              <div className="flex items-center gap-2 text-zinc-500">
                <Timer className="h-4 w-4 text-zinc-400" />
                <span className="text-xs font-medium uppercase tracking-wide">ETA estimado</span>
              </div>
              <p className="mt-2 text-2xl font-bold tabular-nums text-white">
                {formatEta(result.tiempo_estimado_min)}
              </p>
              <p className="text-xs text-zinc-500">Tiempo de conducción estimado</p>
            </div>
            <div className="rounded-2xl border border-zinc-800/80 bg-zinc-900/40 p-4">
              <div className="flex items-center gap-2 text-zinc-500">
                <CircleDollarSign className="h-4 w-4 text-zinc-400" />
                <span className="text-xs font-medium uppercase tracking-wide">Coste operativo</span>
              </div>
              <p className="mt-2 text-2xl font-bold tabular-nums text-white">
                {formatEur(result.coste_operativo_estimado)}
              </p>
              <p className="text-xs text-zinc-500">Estimado según histórico de la empresa</p>
            </div>
            <div
              className={`rounded-2xl border p-4 ${
                result.es_rentable === true
                  ? "border-emerald-500/40 bg-emerald-500/10"
                  : result.es_rentable === false
                    ? "border-red-500/40 bg-red-500/10"
                    : "border-zinc-800/80 bg-zinc-900/40"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-zinc-500">
                  <span className="text-xs font-medium uppercase tracking-wide">Margen proyectado</span>
                </div>
                {result.es_rentable === true || result.es_rentable === false ? (
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
                      result.es_rentable
                        ? "bg-emerald-500/25 text-emerald-300"
                        : "bg-red-500/25 text-red-200"
                    }`}
                    title={
                      result.es_rentable
                        ? "Oferta superior al coste operativo estimado"
                        : "Oferta por debajo del coste operativo estimado"
                    }
                  >
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${
                        result.es_rentable
                          ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]"
                          : "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.7)]"
                      }`}
                    />
                    {result.es_rentable ? "Rentable" : "No rentable"}
                  </span>
                ) : (
                  <span className="rounded-full bg-zinc-800/80 px-2.5 py-1 text-xs font-medium text-zinc-400">
                    Indica precio oferta
                  </span>
                )}
              </div>
              <p className="mt-2 text-2xl font-bold tabular-nums text-white">
                {formatEur(result.margen_proyectado)}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-zinc-400">
                {Number.isFinite(precioNum) && precioNum > 0 ? (
                  <>
                    Diferencial oferta − coste operativo (Math Engine). Remanente:{" "}
                    <span className="font-medium text-zinc-200">
                      {margenSobreOferta !== null ? formatEur(margenSobreOferta) : "—"}
                    </span>
                    .
                  </>
                ) : (
                  <>
                    Proyección por histórico: margen operativo medio por km de tu empresa × distancia de la ruta
                    (sin precio de oferta).
                  </>
                )}
              </p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
