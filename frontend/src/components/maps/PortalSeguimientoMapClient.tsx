"use client";

import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";

import { api } from "@/lib/api";
import type { GeoActivityPunto } from "@/lib/api";

/**
 * Mapas de seguimiento (portal cliente).
 *
 * RGPD / privacidad (Fase 7): el cliente solo ve geostamps de sus propios portes
 * devueltos por la API propia; las teselas base son OpenStreetMap (sin enviar al
 * navegador la clave de Google Maps). La política de privacidad menciona proveedores
 * de mapas para geocodificación en backend; esta vista no invoca la API de Google
 * desde el dispositivo del usuario.
 */
export default function PortalSeguimientoMapClient() {
  const [puntos, setPuntos] = useState<GeoActivityPunto[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.analytics.getGeoActivity();
        if (!cancelled) setPuntos(res.puntos ?? []);
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

  const center = useMemo<[number, number]>(() => {
    const first = puntos[0];
    if (first) return [first.latitud, first.longitud];
    return [40.4168, -3.7038];
  }, [puntos]);

  if (loading) {
    return <p className="text-sm text-zinc-500">Cargando mapa…</p>;
  }
  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }
  if (puntos.length === 0) {
    return (
      <p className="text-sm text-zinc-600">
        Aún no hay entregas georreferenciadas. Los marcadores aparecerán cuando los portes
        entregados tengan coordenadas de destino guardadas.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-zinc-500">
        Teselas: OpenStreetMap. Datos: coordenadas de porte almacenadas en AB Logistics (sin
        geocodificación en tiempo real en este mapa).
      </p>
      <div className="h-[420px] w-full overflow-hidden rounded-xl border border-zinc-200 shadow-sm">
        <MapContainer center={center} zoom={6} className="h-full w-full" scrollWheelZoom>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {puntos.map((p) => (
            <CircleMarker
              key={`${p.id_porte}-${p.tipo_evento}`}
              center={[p.latitud, p.longitud]}
              radius={9}
              pathOptions={{
                color: "#2563eb",
                fillColor: "#3b82f6",
                fillOpacity: 0.85,
                weight: 2,
              }}
            >
              <Tooltip direction="top" offset={[0, -6]} opacity={1} permanent={false}>
                Porte {p.id_porte.slice(0, 8)}… ·{" "}
                {p.margen_operativo != null
                  ? `Margen operativo: ${p.margen_operativo.toLocaleString("es-ES", {
                      style: "currency",
                      currency: "EUR",
                    })}`
                  : "Margen no disponible para su perfil"}
              </Tooltip>
              <Popup>
                <div className="text-xs">
                  <div>
                    <strong>Entrega</strong>
                  </div>
                  <div>ID porte: {p.id_porte}</div>
                  {p.margen_operativo != null && <div>Margen operativo: {p.margen_operativo} €</div>}
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
