"use client";

import L from "leaflet";
import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.heat";

import { api } from "@/lib/api";
import type { GeoHeatCell } from "@/lib/api";

function HeatmapLayer({ points }: { points: [number, number, number][] }) {
  const map = useMap();

  useEffect(() => {
    if (!points.length) return;
    const layer = L.heatLayer(points, {
      radius: 32,
      blur: 22,
      maxZoom: 14,
      max: 1,
      gradient: { 0.2: "blue", 0.5: "lime", 0.7: "yellow", 1: "red" },
    });
    map.addLayer(layer);
    return () => {
      map.removeLayer(layer);
    };
  }, [map, points]);

  return null;
}

/**
 * Mapa de calor administrativo (densidad de portes por zona + ticket medio de gastos).
 *
 * Privacidad: teselas OSM; agregados por celda (~1 km) para no exponer direcciones exactas
 * en el tooltip más allá del bucketing ya aplicado en servidor.
 */
export default function AdminHeatmapMapClient() {
  const [cells, setCells] = useState<GeoHeatCell[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.analytics.getGeoActivity();
        if (!cancelled) setCells(res.heatmap ?? []);
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : "No se pudo cargar el mapa");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const heatPoints = useMemo(
    () => cells.map((c) => [c.latitud, c.longitud, Math.max(0.05, c.intensidad)] as [number, number, number]),
    [cells],
  );

  const center = useMemo<[number, number]>(() => {
    const c = cells[0];
    if (c) return [c.latitud, c.longitud];
    return [40.4168, -3.7038];
  }, [cells]);

  if (loading) {
    return <p className="text-sm text-zinc-400">Cargando mapa de calor…</p>;
  }
  if (error) {
    return <p className="text-sm text-red-400">{error}</p>;
  }
  if (!cells.length) {
    return (
      <p className="text-sm text-zinc-400">
        No hay celdas con coordenadas de entrega suficientes para el mapa de calor.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-zinc-500">
        Capa de calor: densidad de portes por celda geográfica. Tooltip: ticket medio de gastos
        imputados a portes en esa zona (detección de ineficiencias). Teselas OpenStreetMap (sin
        Mapbox/Google en cliente).
      </p>
      <div className="h-[520px] w-full overflow-hidden rounded-xl border border-zinc-800/60 bg-zinc-900/40">
        <MapContainer center={center} zoom={5} className="h-full w-full" scrollWheelZoom>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {heatPoints.length > 0 ? <HeatmapLayer points={heatPoints} /> : null}
          {cells.map((c, idx) => (
            <CircleMarker
              key={`${c.latitud}-${c.longitud}-${idx}`}
              center={[c.latitud, c.longitud]}
              radius={10 + c.intensidad * 24}
              pathOptions={{
                color: "#10b981",
                fillColor: "#34d399",
                fillOpacity: 0.08,
                weight: 1,
                opacity: 0.35,
              }}
            >
              <Tooltip sticky direction="top" opacity={1}>
                <div className="text-xs text-zinc-900">
                  <div>
                    <strong>Ticket gasto medio (zona)</strong>
                  </div>
                  <div>
                    {c.ticket_gasto_medio.toLocaleString("es-ES", { style: "currency", currency: "EUR" })}
                  </div>
                  <div>Portes en celda: {c.portes_en_celda}</div>
                  <div>Intensidad relativa: {(c.intensidad * 100).toFixed(0)}%</div>
                </div>
              </Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
