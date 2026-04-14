"use client";

import { useEffect } from "react";
import { APIProvider, Map, useMap } from "@vis.gl/react-google-maps";

function DirectionsLayer({
  origin,
  destination,
}: {
  origin: string;
  destination: string;
}) {
  const map = useMap();

  useEffect(() => {
    if (!map || !origin?.trim() || !destination?.trim()) return;

    const ds = new google.maps.DirectionsService();
    const dr = new google.maps.DirectionsRenderer({
      map,
      suppressMarkers: false,
    });

    ds.route(
      {
        origin: origin.trim(),
        destination: destination.trim(),
        travelMode: google.maps.TravelMode.DRIVING,
      },
      (result, status) => {
        if (status === "OK" && result) {
          dr.setDirections(result);
        }
      },
    );

    return () => {
      dr.setMap(null);
    };
  }, [map, origin, destination]);

  return null;
}

const defaultCenter = { lat: 40.4168, lng: -3.7038 };

export type RouteMapProps = {
  origin: string;
  destination: string;
};

/**
 * Ruta A→B con Directions (requiere Maps JavaScript API + Directions en el proyecto GCP).
 * Clave: NEXT_PUBLIC_MAPS_API_KEY con restricción HTTP referrer al dominio del front.
 */
export function RouteMap({ origin, destination }: RouteMapProps) {
  const apiKey =
    process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ||
    process.env.NEXT_PUBLIC_MAPS_API_KEY ||
    "";

  if (!apiKey) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50/90 px-4 py-3 text-sm text-amber-900">
        Configura <code className="font-mono text-xs">NEXT_PUBLIC_MAPS_API_KEY</code> y
        restricciones de referrer en Google Cloud para ver el mapa de ruta.
      </div>
    );
  }

  return (
    <APIProvider apiKey={apiKey} libraries={["routes"]}>
      <div className="h-[min(360px,55vh)] w-full min-h-[280px] overflow-hidden rounded-xl border border-zinc-200/80 shadow-sm [&_.map]:!h-full">
        <Map
          defaultCenter={defaultCenter}
          defaultZoom={6}
          gestureHandling="greedy"
          disableDefaultUI={false}
          style={{ width: "100%", height: "100%" }}
        >
          <DirectionsLayer origin={origin} destination={destination} />
        </Map>
      </div>
    </APIProvider>
  );
}
