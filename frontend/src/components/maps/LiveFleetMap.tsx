"use client";

import { GoogleMap, InfoWindow, Marker, useJsApiLoader } from "@react-google-maps/api";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { LiveFleetVehicle } from "@/lib/api";

const MAP_CONTAINER_STYLE = { width: "100%", height: "100%" };

/** Estilo mapa nocturno (Dark Enterprise). */
const DARK_MAP_STYLES: google.maps.MapTypeStyle[] = [
  { elementType: "geometry", stylers: [{ color: "#1d1f23" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#1d1f23" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#8f97a3" }] },
  { featureType: "administrative", elementType: "geometry", stylers: [{ color: "#31343a" }] },
  { featureType: "poi", elementType: "labels.text.fill", stylers: [{ color: "#7a828e" }] },
  { featureType: "road", elementType: "geometry", stylers: [{ color: "#2a2d33" }] },
  { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#3b414b" }] },
  { featureType: "road.highway", elementType: "geometry.stroke", stylers: [{ color: "#242730" }] },
  { featureType: "transit", elementType: "geometry", stylers: [{ color: "#2a2d33" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#111827" }] },
];

const DEFAULT_CENTER = { lat: 40.4168, lng: -3.7038 };

function formatGpsAgo(iso: string | null | undefined): string {
  if (!iso) return "Sin actualización GPS reciente";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "Sin actualización GPS reciente";
  const diff = Date.now() - t;
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "Hace un momento";
  if (m < 60) return `Hace ${m} minuto${m === 1 ? "" : "s"}`;
  const h = Math.floor(m / 60);
  if (h < 24) return `Hace ${h} hora${h === 1 ? "" : "s"}`;
  const d = Math.floor(h / 24);
  return `Hace ${d} día${d === 1 ? "" : "s"}`;
}

function markerColor(estado: LiveFleetVehicle["estado"]): string {
  if (estado === "En Ruta") return "#3b82f6";
  if (estado === "Taller") return "#ef4444";
  return "#22c55e";
}

function buildCircleIcon(color: string): google.maps.Icon {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="${color}" stroke="#ffffff" stroke-width="2"/></svg>`;
  return {
    url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`,
    scaledSize: new google.maps.Size(28, 28),
    anchor: new google.maps.Point(14, 14),
  };
}

export type LiveFleetMapProps = {
  vehicles: LiveFleetVehicle[];
  focusVehicleId: string | null;
  selectedVehicleId: string | null;
  onSelectVehicle: (id: string | null) => void;
  loading?: boolean;
  error?: string | null;
};

export function LiveFleetMap({
  vehicles,
  focusVehicleId,
  selectedVehicleId,
  onSelectVehicle,
  loading = false,
  error = null,
}: LiveFleetMapProps) {
  const apiKey =
    process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ||
    process.env.NEXT_PUBLIC_MAPS_API_KEY ||
    "";

  const mapRef = useRef<google.maps.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);

  const { isLoaded, loadError } = useJsApiLoader({
    id: "live-fleet-map-loader",
    googleMapsApiKey: apiKey,
    libraries: ["places"],
  });

  const withCoords = useMemo(
    () =>
      vehicles.filter(
        (v) =>
          v.ultima_latitud != null &&
          v.ultima_longitud != null &&
          !Number.isNaN(v.ultima_latitud) &&
          !Number.isNaN(v.ultima_longitud),
      ),
    [vehicles],
  );

  const center = useMemo(() => {
    if (!withCoords.length) return DEFAULT_CENTER;
    const lat =
      withCoords.reduce((a, v) => a + (v.ultima_latitud as number), 0) / withCoords.length;
    const lng =
      withCoords.reduce((a, v) => a + (v.ultima_longitud as number), 0) / withCoords.length;
    return { lat, lng };
  }, [withCoords]);

  const onMapLoad = useCallback((map: google.maps.Map) => {
    mapRef.current = map;
    setMapReady(true);
  }, []);

  useEffect(() => {
    if (!mapReady || !mapRef.current || !focusVehicleId) return;
    const v = vehicles.find((x) => x.id === focusVehicleId);
    if (
      v?.ultima_latitud == null ||
      v?.ultima_longitud == null ||
      Number.isNaN(v.ultima_latitud) ||
      Number.isNaN(v.ultima_longitud)
    ) {
      return;
    }
    mapRef.current.panTo({ lat: v.ultima_latitud, lng: v.ultima_longitud });
    const z = mapRef.current.getZoom();
    if (z !== undefined && z < 12) {
      mapRef.current.setZoom(12);
    }
  }, [focusVehicleId, vehicles, mapReady]);

  if (!apiKey) {
    return (
      <div className="flex h-full min-h-[420px] w-full items-center justify-center rounded-2xl border border-zinc-700/80 bg-zinc-900/90 px-6 py-10 text-center">
        <div className="max-w-md space-y-2">
          <p className="text-base font-semibold text-zinc-100">Configuración de mapa requerida</p>
          <p className="text-sm text-zinc-400">
            Defina la variable de entorno{" "}
            <code className="rounded bg-zinc-950 px-1.5 py-0.5 font-mono text-xs text-emerald-400">
              NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
            </code>{" "}
            para cargar el centro de mando sobre Google Maps.
          </p>
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex h-full min-h-[420px] items-center justify-center rounded-2xl border border-red-900/50 bg-red-950/30 px-4 text-sm text-red-200">
        No se pudo cargar Google Maps. Revise la clave API y los orígenes permitidos.
      </div>
    );
  }

  if (!isLoaded) {
    return (
      <div className="flex h-full min-h-[420px] items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-950/80 text-sm text-zinc-400">
        Inicializando mapa…
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-full min-h-[420px] items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-950/80 text-sm text-zinc-400">
        Obteniendo posiciones…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full min-h-[420px] items-center justify-center rounded-2xl border border-amber-900/50 bg-amber-950/20 px-4 text-center text-sm text-amber-100">
        {error}
      </div>
    );
  }

  const selected = vehicles.find((v) => v.id === selectedVehicleId) ?? null;

  return (
    <GoogleMap
      mapContainerStyle={MAP_CONTAINER_STYLE}
      center={center}
      zoom={withCoords.length ? 8 : 6}
      onLoad={onMapLoad}
      options={{
        styles: DARK_MAP_STYLES,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
        disableDefaultUI: false,
      }}
    >
      {withCoords.map((v) => (
        <Marker
          key={v.id}
          position={{ lat: v.ultima_latitud as number, lng: v.ultima_longitud as number }}
          icon={buildCircleIcon(markerColor(v.estado))}
          onClick={() => onSelectVehicle(v.id)}
        />
      ))}
      {selected &&
        selected.ultima_latitud != null &&
        selected.ultima_longitud != null && (
          <InfoWindow
            position={{
              lat: selected.ultima_latitud,
              lng: selected.ultima_longitud,
            }}
            onCloseClick={() => onSelectVehicle(null)}
          >
            <div className="max-w-[220px] p-1 text-zinc-900">
              <p className="font-bold">{selected.matricula}</p>
              <p className="text-sm">
                Conductor: {selected.conductor_nombre?.trim() || "—"}
              </p>
              <p className="text-sm">Estado: {selected.estado}</p>
              <p className="text-xs text-zinc-600">
                GPS: {formatGpsAgo(selected.ultima_actualizacion_gps)}
              </p>
            </div>
          </InfoWindow>
        )}
    </GoogleMap>
  );
}
