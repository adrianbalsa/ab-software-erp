"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { APIProvider, Map, useMap } from "@vis.gl/react-google-maps";

import { geocodeAddressWithCache, type PorteListRow } from "@/lib/api";

const COST_EUR_PER_KM = 0.62;

export type VampireMapPorte = PorteListRow & {
  lat_origin?: number | null;
  lng_origin?: number | null;
  lat_dest?: number | null;
  lng_dest?: number | null;
  real_distance_meters?: number | null;
};

function kmForEconomics(p: VampireMapPorte): number {
  if (p.real_distance_meters != null && p.real_distance_meters > 0) {
    return p.real_distance_meters / 1000;
  }
  return Number(p.km_estimados ?? 0);
}

/** Rentabilidad operativa estimada: ingreso / coste × 100. */
export function routeEfficiencyPercent(p: VampireMapPorte): number | null {
  const income = Number(p.precio_pactado ?? 0);
  const cost = kmForEconomics(p) * COST_EUR_PER_KM;
  if (cost <= 0) return null;
  return (income / cost) * 100;
}

function formatEur(n: number) {
  return new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);
}

function routeEbitdaEstimated(p: VampireMapPorte): number {
  const income = Number(p.precio_pactado ?? 0);
  return income - kmForEconomics(p) * COST_EUR_PER_KM;
}

export type ResolvedRoute = {
  id: string;
  o: google.maps.LatLngLiteral;
  d: google.maps.LatLngLiteral;
  efficiencyPct: number | null;
  ebitda: number;
  label: string;
};

function midpoint(a: google.maps.LatLngLiteral, b: google.maps.LatLngLiteral): google.maps.LatLngLiteral {
  return { lat: (a.lat + b.lat) / 2, lng: (a.lng + b.lng) / 2 };
}

function PolylinesLayer({ portes, resolved }: { portes: VampireMapPorte[]; resolved: ResolvedRoute[] }) {
  const map = useMap();
  const iwRef = useRef<google.maps.InfoWindow | null>(null);

  const idToPe = useMemo(() => {
    const m = new globalThis.Map<string, ResolvedRoute>();
    for (const r of resolved) m.set(r.id, r);
    return m;
  }, [resolved]);

  useEffect(() => {
    if (!map) return;
    if (!iwRef.current) {
      iwRef.current = new google.maps.InfoWindow();
    }
    const polys: google.maps.Polyline[] = [];
    const listeners: google.maps.MapsEventListener[] = [];

    for (const p of portes) {
      const row = idToPe.get(p.id);
      if (!row) continue;
      const eff = row.efficiencyPct;
      let strokeColor = "#eab308";
      if (eff != null) {
        if (eff > 90) strokeColor = "#22c55e";
        else if (eff < 70) strokeColor = "#ef4444";
      }
      const line = new google.maps.Polyline({
        path: [row.o, row.d],
        geodesic: true,
        strokeColor,
        strokeOpacity: 0.95,
        strokeWeight: 4,
        map,
      });
      const html = `<div style="font-size:12px;max-width:240px;color:#18181b">
        <strong>${row.label}</strong><br/>
        EBITDA est.: ${formatEur(row.ebitda)}<br/>
        ${eff != null ? `Eficiencia: ${eff.toFixed(1)}%` : "Eficiencia: N/D"}
      </div>`;
      const pos = midpoint(row.o, row.d);
      listeners.push(
        line.addListener("mouseover", () => {
          iwRef.current?.setContent(html);
          iwRef.current?.setPosition(pos);
          iwRef.current?.open({ map, shouldFocus: false });
        }),
      );
      listeners.push(
        line.addListener("mouseout", () => {
          iwRef.current?.close();
        }),
      );
      polys.push(line);
    }

    return () => {
      listeners.forEach((l) => l.remove());
      polys.forEach((pl) => pl.setMap(null));
      iwRef.current?.close();
    };
  }, [map, portes, idToPe]);

  return null;
}

function MapScene({
  portes,
  resolved,
  mapKey,
  defaultCenter,
  defaultZoom,
}: {
  portes: VampireMapPorte[];
  resolved: ResolvedRoute[];
  mapKey: string;
  defaultCenter: google.maps.LatLngLiteral;
  defaultZoom: number;
}) {
  return (
    <Map
      key={mapKey}
      defaultCenter={defaultCenter}
      defaultZoom={defaultZoom}
      gestureHandling="greedy"
      disableDefaultUI={false}
      style={{ width: "100%", height: "100%" }}
    >
      <PolylinesLayer portes={portes} resolved={resolved} />
    </Map>
  );
}

export type VampireMapProps = {
  portes: VampireMapPorte[];
  /** Altura CSS del contenedor del mapa */
  className?: string;
};

function VampireMapInner({ portes, className }: VampireMapProps) {
  const [resolved, setResolved] = useState<ResolvedRoute[]>([]);
  const [resolving, setResolving] = useState(false);
  const [geoErr, setGeoErr] = useState<string | null>(null);

  const runGeocode = useCallback(async () => {
    if (portes.length === 0) {
      setResolved([]);
      return;
    }
    if (typeof google === "undefined" || !google.maps?.Geocoder) {
      return;
    }
    setResolving(true);
    setGeoErr(null);
    try {
      const geocoder = new google.maps.Geocoder();
      const out: ResolvedRoute[] = [];
      for (const p of portes) {
        let oLat = p.lat_origin ?? null;
        let oLng = p.lng_origin ?? null;
        let dLat = p.lat_dest ?? null;
        let dLng = p.lng_dest ?? null;
        if (oLat == null || oLng == null) {
          const g = await geocodeAddressWithCache(geocoder, p.origen);
          if (g) {
            oLat = g.lat;
            oLng = g.lng;
          }
        }
        if (dLat == null || dLng == null) {
          const g = await geocodeAddressWithCache(geocoder, p.destino);
          if (g) {
            dLat = g.lat;
            dLng = g.lng;
          }
        }
        if (oLat == null || oLng == null || dLat == null || dLng == null) continue;
        out.push({
          id: p.id,
          o: { lat: oLat, lng: oLng },
          d: { lat: dLat, lng: dLng },
          efficiencyPct: routeEfficiencyPercent(p),
          ebitda: routeEbitdaEstimated(p),
          label: `${p.origen} → ${p.destino}`,
        });
      }
      setResolved(out);
    } catch (e) {
      setGeoErr(e instanceof Error ? e.message : "No se pudieron geocodificar rutas");
      setResolved([]);
    } finally {
      setResolving(false);
    }
  }, [portes]);

  useEffect(() => {
    if (typeof google !== "undefined" && google.maps?.Geocoder) {
      void runGeocode();
      return;
    }
    const id = window.setInterval(() => {
      if (typeof google !== "undefined" && google.maps?.Geocoder) {
        window.clearInterval(id);
        void runGeocode();
      }
    }, 100);
    return () => window.clearInterval(id);
  }, [runGeocode]);

  const defaultCenter = useMemo((): google.maps.LatLngLiteral => {
    if (resolved.length === 0) return { lat: 40.4168, lng: -3.7038 };
    const lat = resolved.reduce((s, r) => s + (r.o.lat + r.d.lat) / 2, 0) / resolved.length;
    const lng = resolved.reduce((s, r) => s + (r.o.lng + r.d.lng) / 2, 0) / resolved.length;
    return { lat, lng };
  }, [resolved]);

  const defaultZoom = resolved.length === 1 ? 7 : 6;
  const mapKey = resolved.map((r) => r.id).join("|") || "empty";

  return (
    <div
      className={
        className ??
        "relative h-[min(420px,55vh)] w-full min-h-[300px] overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950"
      }
    >
      {(resolving || geoErr) && (
        <div className="absolute left-3 top-3 z-[1] rounded-md border border-zinc-700 bg-zinc-950/90 px-2 py-1 text-xs text-zinc-300">
          {resolving ? "Geocodificando rutas…" : null}
          {geoErr ? <span className="text-red-300">{geoErr}</span> : null}
        </div>
      )}
      <MapScene
        portes={portes}
        resolved={resolved}
        mapKey={mapKey}
        defaultCenter={defaultCenter}
        defaultZoom={defaultZoom}
      />
    </div>
  );
}

/**
 * Mapa de rutas activas: verde (eficiencia &gt; 90%), rojo (&lt; 70%), ámbar intermedio.
 * Tooltip: EBITDA estimado (ingreso − coste a 0,62 €/km sobre km real o estimado).
 */
export function VampireMap({ portes, className }: VampireMapProps) {
  const apiKey =
    process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || process.env.NEXT_PUBLIC_MAPS_API_KEY || "";

  if (!apiKey) {
    return (
      <div
        className={
          className ??
          "flex min-h-[280px] items-center rounded-xl border border-amber-900/50 bg-amber-950/40 px-4 py-3 text-sm text-amber-100"
        }
      >
        Configura{" "}
        <code className="mx-1 font-mono text-xs">NEXT_PUBLIC_GOOGLE_MAPS_API_KEY</code> para el mapa del Vampire Radar.
      </div>
    );
  }

  return (
    <APIProvider apiKey={apiKey} libraries={["geocoding", "routes"]}>
      <VampireMapInner portes={portes} className={className} />
    </APIProvider>
  );
}
