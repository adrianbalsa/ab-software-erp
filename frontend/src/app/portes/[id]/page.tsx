"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { RouteMap } from "@/components/maps/RouteMap";
import { API_BASE, authHeaders } from "@/lib/api";

type PorteDetail = {
  id: string;
  origen: string;
  destino: string;
  km_estimados: number;
  precio_pactado: number;
  fecha: string;
  estado: string;
};

export default function PorteDetailPage() {
  const params = useParams();
  const id = typeof params?.id === "string" ? params.id : "";

  const [porte, setPorte] = useState<PorteDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/portes/${encodeURIComponent(id)}`, {
        credentials: "include",
        headers: { ...authHeaders() },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }
      setPorte((await res.json()) as PorteDetail);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
      setPorte(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!id) {
    return (
      <div className="min-h-screen ab-app-gradient p-8">
        <p className="text-slate-600">ID inválido.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen ab-app-gradient pb-12">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 pt-8">
        <div className="flex items-center gap-4 mb-6">
          <Link
            href="/portes"
            className="text-sm font-medium text-blue-600 hover:text-blue-800"
          >
            ← Volver a portes
          </Link>
        </div>

        {loading && (
          <div className="ab-card rounded-2xl p-12 text-center text-slate-500">
            Cargando porte…
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        )}

        {porte && !loading && (
          <div className="space-y-6">
            <div className="ab-card rounded-2xl p-6">
              <h1 className="text-xl font-bold text-slate-900">Detalle del porte</h1>
              <p className="text-sm text-slate-500 mt-1 font-mono">{porte.id}</p>
              <dl className="mt-4 grid gap-2 text-sm">
                <div className="flex items-baseline gap-2">
                  <dt className="text-slate-500 w-28 shrink-0">Fecha</dt>
                  <dd className="font-medium text-slate-800">{porte.fecha}</dd>
                </div>
                <div className="flex items-baseline gap-2">
                  <dt className="text-slate-500 w-28 shrink-0">Estado</dt>
                  <dd className="font-medium text-slate-800">{porte.estado}</dd>
                </div>
                <div className="flex items-baseline gap-2">
                  <dt className="text-slate-500 w-28 shrink-0">Km</dt>
                  <dd className="font-mono font-medium text-slate-800">
                    {Number(porte.km_estimados).toLocaleString("es-ES", {
                      maximumFractionDigits: 2,
                    })}{" "}
                    km
                  </dd>
                </div>
                <div className="flex items-baseline gap-2">
                  <dt className="text-slate-500 w-28 shrink-0">Precio</dt>
                  <dd className="font-mono font-medium text-slate-800">
                    {Number(porte.precio_pactado).toFixed(2)} €
                  </dd>
                </div>
                <div className="flex flex-col gap-1 sm:flex-row sm:gap-2">
                  <dt className="text-slate-500 w-28 shrink-0">Origen</dt>
                  <dd className="text-slate-800">{porte.origen}</dd>
                </div>
                <div className="flex flex-col gap-1 sm:flex-row sm:gap-2">
                  <dt className="text-slate-500 w-28 shrink-0">Destino</dt>
                  <dd className="text-slate-800">{porte.destino}</dd>
                </div>
              </dl>
            </div>

            <div className="ab-card rounded-2xl p-6">
              <h2 className="text-lg font-bold text-slate-800 mb-1">Ruta</h2>
              <p className="text-xs text-slate-500 mb-4">
                Visualización con Google Maps Directions (clave de navegador con referrer
                restringido).
              </p>
              <RouteMap origin={porte.origen} destination={porte.destino} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
