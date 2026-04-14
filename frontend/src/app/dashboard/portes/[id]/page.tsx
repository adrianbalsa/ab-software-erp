"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Download, Leaf, Loader2, MapPin, Truck } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { api, type PorteDetailOut } from "@/lib/api";
import { generateEsgCertificadoFromPorte } from "@/lib/esgGenerator";

function formatKg(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return `${Number(value).toLocaleString("es-ES", { maximumFractionDigits: 2 })} kg`;
}

export default function DashboardPorteDetailPage() {
  const params = useParams();
  const id = typeof params?.id === "string" ? params.id : "";

  const [porte, setPorte] = useState<PorteDetailOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [esgDownloading, setEsgDownloading] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      setPorte(await api.portes.get(id));
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

  const descargarEsg = async () => {
    if (!porte) return;
    setEsgDownloading(true);
    try {
      const blob = await generateEsgCertificadoFromPorte(porte);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Certificado_Huella_CO2_porte_${String(porte.id).slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "No se pudo generar el certificado ESG");
    } finally {
      setEsgDownloading(false);
    }
  };

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

        <header className="mb-8 flex flex-col gap-4 border-b border-zinc-800 pb-6 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              <Truck className="h-4 w-4 text-emerald-500/90" aria-hidden />
              Detalle operativo
            </div>
            <h1 className="mt-2 font-serif text-2xl font-semibold tracking-tight text-zinc-50">Porte</h1>
            <p className="mt-1 font-mono text-xs text-zinc-500">{id || "—"}</p>
          </div>
          <button
            type="button"
            disabled={!porte || esgDownloading}
            onClick={() => void descargarEsg()}
            className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-xl border border-emerald-700/50 bg-emerald-950/40 px-4 py-2.5 text-sm font-semibold text-emerald-100 shadow-sm hover:bg-emerald-900/50 disabled:opacity-50"
          >
            {esgDownloading ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Download className="h-4 w-4" aria-hidden />
            )}
            Descargar certificado ESG
          </button>
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
              <div className="min-w-0 space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Huella CO₂ (GLEC · motor declarado)
                </p>
                <p className="text-sm tabular-nums text-emerald-200/95">
                  {porte.esg_co2_total_kg != null
                    ? `${Number(porte.esg_co2_total_kg).toLocaleString("es-ES", { maximumFractionDigits: 3 })} kg`
                    : formatKg(porte.co2_emitido)}
                </p>
                {porte.esg_co2_euro_iii_baseline_kg != null && (
                  <p className="text-xs text-zinc-400">
                    Referencia Euro III (mismo recorrido):{" "}
                    <span className="font-mono text-zinc-200">
                      {Number(porte.esg_co2_euro_iii_baseline_kg).toLocaleString("es-ES", {
                        maximumFractionDigits: 3,
                      })}{" "}
                      kg
                    </span>
                    {porte.esg_co2_ahorro_vs_euro_iii_kg != null ? (
                      <>
                        {" "}
                        · Ahorro:{" "}
                        <span className="font-mono text-emerald-300/95">
                          {Number(porte.esg_co2_ahorro_vs_euro_iii_kg).toLocaleString("es-ES", {
                            maximumFractionDigits: 3,
                          })}{" "}
                          kg
                        </span>
                      </>
                    ) : null}
                  </p>
                )}
                {(porte.vehiculo_matricula || porte.vehiculo_normativa_euro) && (
                  <p className="text-[11px] text-zinc-500">
                    {[porte.vehiculo_matricula, porte.vehiculo_normativa_euro].filter(Boolean).join(" · ")}
                  </p>
                )}
                <p className="text-[11px] text-zinc-600">
                  Km del registro del porte (habitualmente vía Google Directions en cotización). Certificado
                  descargable para auditorías ISO 14001.
                </p>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
