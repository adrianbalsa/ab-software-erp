"use client";

import { useMemo, useState } from "react";
import { GoogleMap, InfoWindow, Marker, Polyline, useJsApiLoader } from "@react-google-maps/api";
import { Clock, TrendingUp } from "lucide-react";

type FleetMapPorte = {
  id: string;
  origin: string;
  destination: string;
  estimatedMargin: number;
  originCoords?: { lat: number; lng: number };
  destCoords?: { lat: number; lng: number };
  eta?: string;
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

const ORIGIN_ICON: google.maps.Icon = {
  url:
    "data:image/svg+xml;utf8," +
    encodeURIComponent(
      "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'>" +
        "<circle cx='12' cy='12' r='8' fill='#3b82f6'/>" +
        "<circle cx='12' cy='12' r='4' fill='#ffffff'/>" +
      "</svg>",
    ),
  scaledSize: new google.maps.Size(32, 32),
};

const DESTINATION_ICON: google.maps.Icon = {
  url:
    "data:image/svg+xml;utf8," +
    encodeURIComponent(
      "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'>" +
        "<path d='M12 2L2 7v10c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-10-5z' fill='#ef4444'/>" +
        "<circle cx='12' cy='12' r='3' fill='#ffffff'/>" +
      "</svg>",
    ),
  scaledSize: new google.maps.Size(32, 32),
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

  const routePolylines = useMemo(() => {
    return trucks
      .filter(
        (truck) =>
          truck.porte.originCoords &&
          truck.porte.destCoords &&
          truck.porte.originCoords.lat !== 0 &&
          truck.porte.originCoords.lng !== 0,
      )
      .map((truck) => ({
        truckId: truck.id,
        path: [truck.porte.originCoords!, truck.position, truck.porte.destCoords!],
      }));
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

        {trucks.map((truck) => {
          if (!truck.porte.originCoords || truck.porte.originCoords.lat === 0) return null;
          return (
            <Marker
              key={`origin-${truck.id}`}
              position={truck.porte.originCoords}
              icon={ORIGIN_ICON}
              title={truck.porte.origin}
            />
          );
        })}

        {trucks.map((truck) => {
          if (!truck.porte.destCoords || truck.porte.destCoords.lat === 0) return null;
          return (
            <Marker
              key={`dest-${truck.id}`}
              position={truck.porte.destCoords}
              icon={DESTINATION_ICON}
              title={truck.porte.destination}
            />
          );
        })}

        {routePolylines.map((route) => (
          <Polyline
            key={`route-${route.truckId}`}
            path={route.path}
            options={{
              strokeColor: "#10b981",
              strokeOpacity: 0.8,
              strokeWeight: 3,
              geodesic: true,
            }}
          />
        ))}

        {selectedTruck && (
          <InfoWindow position={selectedTruck.position} onCloseClick={() => setSelectedTruckId(null)}>
            <div className="min-w-[240px] text-zinc-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Porte en curso</p>
              <div className="mt-2 space-y-1.5 text-sm">
                <p>
                  <span className="font-semibold">ID:</span> {selectedTruck.porte.id.slice(0, 8)}
                </p>
                <p>
                  <span className="font-semibold">Origen:</span> {selectedTruck.porte.origin}
                </p>
                <p>
                  <span className="font-semibold">Destino:</span> {selectedTruck.porte.destination}
                </p>
                <p className="flex items-center gap-1.5">
                  <TrendingUp className="h-4 w-4 text-emerald-600" />
                  <span className="font-semibold">Margen:</span> {selectedTruck.porte.estimatedMargin.toFixed(2)} €
                </p>
                {selectedTruck.porte.eta && (
                  <p className="flex items-center gap-1.5 rounded bg-blue-50 px-2 py-1 mt-2">
                    <Clock className="h-4 w-4 text-blue-600" />
                    <span className="font-semibold text-blue-900">ETA:</span>
                    <span className="text-blue-700">{selectedTruck.porte.eta}</span>
                  </p>
                )}
              </div>
            </div>
          </InfoWindow>
        )}
      </GoogleMap>
    </div>
  );
}
