"use client";

import { useMemo, useState } from "react";
import { GoogleMap, InfoWindow, Marker, useJsApiLoader } from "@react-google-maps/api";

type FleetMapPorte = {
  id: string;
  origin: string;
  destination: string;
  estimatedMargin: number;
};

export type FleetMapTruck = {
  id: string;
  position: {
    lat: number;
    lng: number;
  };
  porte: FleetMapPorte;
};

export type FleetMapProps = {
  trucks: FleetMapTruck[];
  loading?: boolean;
  error?: string | null;
  heightPx?: number;
};

const DEFAULT_CENTER = { lat: 40.4168, lng: -3.7038 };
const DEFAULT_ZOOM = 6;

const MAP_CONTAINER_STYLE = {
  width: "100%",
  height: "100%",
};

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

const TRUCK_ICON: google.maps.Icon = {
  url:
    "data:image/svg+xml;utf8," +
    encodeURIComponent(
      "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'>" +
        "<path d='M2 6h11v8h2v-3h4l3 3v4h-2a2 2 0 1 1-4 0h-4a2 2 0 1 1-4 0H6a2 2 0 1 1-4 0V6z' fill='#10b981'/>" +
        "<path d='M13 8h6v3h-6z' fill='#0b1220' fill-opacity='0.8'/>" +
      "</svg>",
    ),
};

export function FleetMap({ trucks, loading = false, error = null, heightPx = 500 }: FleetMapProps) {
  const [selectedTruckId, setSelectedTruckId] = useState<string | null>(null);
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || "";
  const { isLoaded, loadError } = useJsApiLoader({
    id: "fleet-map-script",
    googleMapsApiKey: apiKey,
  });

  const selectedTruck = useMemo(
    () => trucks.find((truck) => truck.id === selectedTruckId) ?? null,
    [trucks, selectedTruckId],
  );

  const center = useMemo(() => {
    if (!trucks.length) return DEFAULT_CENTER;
    const lat = trucks.reduce((acc, truck) => acc + truck.position.lat, 0) / trucks.length;
    const lng = trucks.reduce((acc, truck) => acc + truck.position.lng, 0) / trucks.length;
    return { lat, lng };
  }, [trucks]);

  if (!apiKey) {
    return (
      <div className="flex min-h-[500px] w-full items-center justify-center rounded-2xl border border-amber-700/50 bg-amber-950/40 px-4 py-6 text-center text-sm text-amber-200">
        Configura <code className="mx-1 rounded bg-zinc-900 px-1 py-0.5">NEXT_PUBLIC_GOOGLE_MAPS_API_KEY</code>
        para visualizar tu flota en tiempo real.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex min-h-[500px] w-full items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-900/60 px-4 py-6 text-sm text-zinc-300">
        Cargando posiciones de flota...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-[500px] w-full items-center justify-center rounded-2xl border border-red-700/50 bg-red-950/30 px-4 py-6 text-center text-sm text-red-200">
        No se han podido cargar los activos de flota. {error}
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex min-h-[500px] w-full items-center justify-center rounded-2xl border border-red-700/50 bg-red-950/30 px-4 py-6 text-center text-sm text-red-200">
        Error al inicializar Google Maps. Verifica la API key y las restricciones de dominio.
      </div>
    );
  }

  if (!isLoaded) {
    return (
      <div className="flex min-h-[500px] w-full items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-900/60 px-4 py-6 text-sm text-zinc-300">
        Inicializando entorno cartográfico...
      </div>
    );
  }

  return (
    <div className="w-full overflow-hidden rounded-2xl border border-zinc-800 shadow-2xl shadow-black/35" style={{ height: `${Math.max(heightPx, 500)}px` }}>
      <GoogleMap
        mapContainerStyle={MAP_CONTAINER_STYLE}
        center={center}
        zoom={DEFAULT_ZOOM}
        options={{
          styles: DARK_MAP_STYLES,
          disableDefaultUI: false,
          mapTypeControl: false,
          fullscreenControl: false,
          streetViewControl: false,
          gestureHandling: "greedy",
        }}
      >
        {trucks.map((truck) => (
          <Marker
            key={truck.id}
            position={truck.position}
            icon={TRUCK_ICON}
            title={`Camión ${truck.id}`}
            onClick={() => setSelectedTruckId(truck.id)}
          />
        ))}

        {selectedTruck && (
          <InfoWindow position={selectedTruck.position} onCloseClick={() => setSelectedTruckId(null)}>
            <div className="min-w-[220px] text-zinc-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Porte en curso</p>
              <div className="mt-2 space-y-1.5 text-sm">
                <p>
                  <span className="font-semibold">ID del Porte:</span> {selectedTruck.porte.id}
                </p>
                <p>
                  <span className="font-semibold">Origen:</span> {selectedTruck.porte.origin}
                </p>
                <p>
                  <span className="font-semibold">Destino:</span> {selectedTruck.porte.destination}
                </p>
                <p>
                  <span className="font-semibold">Margen Estimado:</span> {selectedTruck.porte.estimatedMargin} €
                </p>
              </div>
            </div>
          </InfoWindow>
        )}
      </GoogleMap>
    </div>
  );
}
