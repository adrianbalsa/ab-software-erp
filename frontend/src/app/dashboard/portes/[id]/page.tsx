"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Leaf, Loader2, MapPin, Truck } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { API_BASE, apiFetch } from "@/lib/api";

type PorteLite = {
  id: string;
  origen: string;
  destino: string;
  estado: string;
  fecha?: string;
  co2_emitido?: number | null;
};

function formatKg(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return `${Number(value).toLocaleString("es-ES", { maximumFractionDigits: 2 })} kg`;
}

export default function DashboardPorteDetailPage() {
  const params = useParams();
  const id = typeof params?.id === "string" ? params.id : "";

  const [porte, setPorte] = useState<PorteLite | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`${API_BASE}/portes/${encodeURIComponent(id)}`, {
        credentials: "include",
      });
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(typeof err?.detail === "string" ? err.detail : `HTTP ${res.status}`);
      }
      const data = (await res.json()) as Record<string, unknown>;
      setPorte({
        id: String(data.id ?? id),
        origen: String(data.origen ?? ""),
        destino: String(data.destino ?? ""),
        estado: String(data.estado ?? ""),
        fecha: data.fecha != null ? String(data.fecha) : undefined,
        co2_emitido:
          data.co2_emitido != null && data.co2_emitido !== ""
            ? Number(data.co2_emitido)
            : null,
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "No se pudo cargar el porte.");
      setPorte(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <AppShell active="portes">
      <div className="mx-auto w-full max-w-2xl bg-zinc-950 p-6 md:p-10">
        <div className="mb-6 flex flex-wrap items-center gap-3">
          <Link
            href="/portes"
            className="inline-flex items-center gap-2 text-sm font-medium text-zinc-400 transition-colors hover:text-emerald-400"
          >
            <ArrowLeft className="h-4 w-4 shrink-0" aria-hidden />
            Volver a Portes
          </Link>
          <span className="text-zinc-700">·</span>
          <Link
            href="/dashboard/certificaciones"
            className="text-sm font-medium text-zinc-500 transition-colors hover:text-emerald-400"
          >
            Certificaciones
          </Link>
        </div>

        <header className="mb-8 border-b border-zinc-800 pb-6">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
            <Truck className="h-4 w-4 text-emerald-500/90" aria-hidden />
            Detalle operativo
          </div>
          <h1 className="mt-2 font-serif text-2xl font-semibold tracking-tight text-zinc-50">Porte</h1>
          <p className="mt-1 font-mono text-xs text-zinc-500">{id || "—"}</p>
        </header>

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-zinc-400">
            <Loader2 className="h-5 w-5 animate-spin text-emerald-500" aria-hidden />
            Cargando…
          </div>
        ) : error ? (
          <div className="rounded-lg border border-rose-500/35 bg-rose-950/30 px-4 py-3 text-sm text-rose-200">
            {error}
          </div>
        ) : porte ? (
          <div className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
            <div className="flex items-start gap-3">
              <MapPin className="mt-0.5 h-5 w-5 shrink-0 text-zinc-500" aria-hidden />
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Origen</p>
                <p className="text-sm text-zinc-100">{porte.origen || "—"}</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <MapPin className="mt-0.5 h-5 w-5 shrink-0 text-zinc-500" aria-hidden />
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Destino</p>
                <p className="text-sm text-zinc-100">{porte.destino || "—"}</p>
              </div>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Estado</p>
              <p className="mt-1 inline-flex rounded-md border border-zinc-700 bg-zinc-950/60 px-2.5 py-1 text-sm text-zinc-200">
                {porte.estado || "—"}
              </p>
            </div>
            <div className="flex items-start gap-3 border-t border-zinc-800 pt-4">
              <Leaf className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500/80" aria-hidden />
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Emisiones (CO₂)
                </p>
                <p className="text-sm tabular-nums text-emerald-200/95">{formatKg(porte.co2_emitido)}</p>
                <p className="mt-1 text-[11px] text-zinc-600">
                  Estimación operativa según distancia y carga; metodología alineada con reporting ESG.
                </p>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
