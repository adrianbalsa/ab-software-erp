"use client";

import { Star } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AdvancedMarker,
  APIProvider,
  InfoWindow,
  Map,
  useAdvancedMarkerRef,
  useMap,
} from "@vis.gl/react-google-maps";

import type { FlotaInventarioRow, PorteListRow } from "@/lib/api";
import { geocodeAddressWithCache } from "@/lib/api";
import { cn } from "@/lib/utils";
import { getOperationalCostEurKmCached, publicOperationalCostEurKmDefault } from "@/lib/operationalPricing";

import { BUNKER_MAP_STYLES } from "./fleetMapStyles";

const DEFAULT_CENTER: google.maps.LatLngLiteral = { lat: 40.4168, lng: -3.7038 };

export type FleetMarkerKind = "star" | "vampire" | "default";

export type FleetPorteMarker = {
  id: string;
  position: google.maps.LatLngLiteral;
  kind: FleetMarkerKind;
  origen: string;
  destino: string;
  co2Kg: number | null;
  /** Margen operativo estimado (sustituto de EBITDA en UI). */
  margenOpEstEUR: number | null;
  matricula: string | null;
};

function isEuroIII(v: FlotaInventarioRow | undefined): boolean {
  if (!v) return false;
  const ec = String(v.engine_class || "").toUpperCase();
  if (ec === "EURO_III" || ec.includes("III")) return true;
  const ne = String(v.normativa_euro || "");
  if (ne.includes("III") || ne.toLowerCase().includes("euro iii")) return true;
  const cert = String(v.certificacion_emisiones || "");
  return cert.includes("III");
}

function classifyPorte(
  p: PorteListRow,
  vehicle: FlotaInventarioRow | undefined,
  costEurKm: number,
): FleetMarkerKind {
  const km = Math.max(Number(p.km_estimados) || 0, 1);
  const precio = Number(p.precio_pactado) || 0;
  const co2 = p.co2_emitido != null ? Number(p.co2_emitido) : null;
  const eurPerKm = precio / km;
  const co2PerKm = co2 != null ? co2 / km : null;
  const margenKm = eurPerKm - costEurKm;

  const lowMargin = margenKm < 0.28;
  const vampire = isEuroIII(vehicle) || lowMargin;
  if (vampire) return "vampire";

  const highMarginLowCo2 =
    margenKm >= 0.55 && co2PerKm != null && co2PerKm <= 2.1 && co2PerKm >= 0;
  if (highMarginLowCo2) return "star";

  return "default";
}

function midpoint(
  a: google.maps.LatLngLiteral,
  b: google.maps.LatLngLiteral,
): google.maps.LatLngLiteral {
  return { lat: (a.lat + b.lat) / 2, lng: (a.lng + b.lng) / 2 };
}

function margenOperativoEst(p: PorteListRow, costEurKm: number): number | null {
  const km = Math.max(Number(p.km_estimados) || 0, 1);
  const precio = Number(p.precio_pactado) || 0;
  if (precio <= 0) return null;
  return precio - km * costEurKm;
}

type MapInnerProps = {
  portes: PorteListRow[];
  vehiclesById: Record<string, FlotaInventarioRow>;
  costEurKm: number;
  onGeocodingChange?: (busy: boolean) => void;
};

function FleetMapInner({ portes, vehiclesById, costEurKm, onGeocodingChange }: MapInnerProps) {
  const map = useMap();
  const [markers, setMarkers] = useState<FleetPorteMarker[]>([]);
  const [geoError, setGeoError] = useState<string | null>(null);

  useEffect(() => {
    if (!map || typeof google === "undefined" || !google.maps?.Geocoder) return;

    let cancelled = false;
    const geocoder = new google.maps.Geocoder();

    async function run() {
      onGeocodingChange?.(true);
      setGeoError(null);
      const next: FleetPorteMarker[] = [];

      for (const p of portes) {
        if (cancelled) break;
        const vid = p.vehiculo_id ? String(p.vehiculo_id) : "";
        const vehicle = vid ? vehiclesById[vid] : undefined;
        const kind = classifyPorte(p, vehicle, costEurKm);

        const o = await geocodeAddressWithCache(geocoder, p.origen);
        const d = await geocodeAddressWithCache(geocoder, p.destino);
        if (!o || !d) continue;

        const pos = midpoint(o, d);
        const m = margenOperativoEst(p, costEurKm);
        next.push({
          id: p.id,
          position: pos,
          kind,
          origen: p.origen,
          destino: p.destino,
          co2Kg: p.co2_emitido != null ? Number(p.co2_emitido) : null,
          margenOpEstEUR: m,
          matricula: vehicle?.matricula ?? null,
        });
      }

      if (!cancelled) {
        setMarkers(next);
      }
      onGeocodingChange?.(false);
    }

    void run().catch((e: unknown) => {
      if (!cancelled) {
        setGeoError(e instanceof Error ? e.message : "Error de geocodificación");
        onGeocodingChange?.(false);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [map, portes, vehiclesById, costEurKm, onGeocodingChange]);

  useEffect(() => {
    if (!map || markers.length === 0) return;
    const b = new google.maps.LatLngBounds();
    markers.forEach((m) => b.extend(m.position));
    map.fitBounds(b, 56);
  }, [map, markers]);

  return (
    <>
      {geoError ? (
        <div className="absolute left-4 top-4 z-10 max-w-sm rounded-lg border border-amber-500/40 bg-zinc-950/95 px-3 py-2 text-xs text-amber-100 shadow-lg backdrop-blur">
          {geoError}
        </div>
      ) : null}
      {markers.map((m) => (
        <PorteMarker key={m.id} marker={m} />
      ))}
    </>
  );
}

function PorteMarker({ marker }: { marker: FleetPorteMarker }) {
  const [markerRef, markerEl] = useAdvancedMarkerRef();
  const [open, setOpen] = useState(false);
  const onClick = useCallback(() => setOpen(true), []);
  const onClose = useCallback(() => setOpen(false), []);

  const accent = useMemo(() => {
    if (marker.kind === "vampire") return "vampire";
    if (marker.kind === "star") return "star";
    return "default";
  }, [marker.kind]);

  return (
    <>
      <AdvancedMarker ref={markerRef} position={marker.position} onClick={onClick} zIndex={accent === "vampire" ? 80 : 40}>
        {accent === "vampire" ? (
          <div className="relative flex h-11 w-11 cursor-pointer items-center justify-center">
            <span
              className="absolute inline-flex h-10 w-10 animate-ping rounded-full bg-red-500/35"
              aria-hidden
            />
            <div
              className="relative flex h-9 w-9 items-center justify-center rounded-full border-2 border-red-400/80 bg-red-600 shadow-[0_0_20px_rgba(239,68,68,0.55)]"
              title="Riesgo / Euro III"
            >
              <span className="text-[10px] font-black text-white">III</span>
            </div>
          </div>
        ) : accent === "star" ? (
          <div
            className="flex cursor-pointer items-center justify-center drop-shadow-[0_0_14px_rgba(52,211,153,0.85)]"
            title="Alta rentabilidad · bajo CO₂"
          >
            <Star className="h-8 w-8 fill-emerald-400 text-emerald-300" strokeWidth={1.25} aria-hidden />
          </div>
        ) : (
          <div
            className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full border border-emerald-600/70 bg-emerald-500/90 shadow-[0_0_12px_rgba(16,185,129,0.45)]"
            title="Porte activo"
          >
            <span className="h-2 w-2 rounded-full bg-white/90" />
          </div>
        )}
      </AdvancedMarker>
      {open && markerEl ? (
        <InfoWindow anchor={markerEl} onCloseClick={onClose} maxWidth={280}>
          <div className="min-w-[220px] p-1 text-zinc-900">
            <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Porte</p>
            <p className="mt-1 font-mono text-[11px] text-zinc-600">{marker.id.slice(0, 8)}…</p>
            <dl className="mt-2 space-y-1.5 text-xs">
              <div>
                <dt className="font-semibold text-zinc-700">Origen</dt>
                <dd className="text-zinc-900">{marker.origen}</dd>
              </div>
              <div>
                <dt className="font-semibold text-zinc-700">Destino</dt>
                <dd className="text-zinc-900">{marker.destino}</dd>
              </div>
              <div className="flex flex-wrap gap-3 border-t border-zinc-200 pt-2">
                <div>
                  <dt className="text-[10px] font-semibold uppercase text-zinc-500">CO₂</dt>
                  <dd className="tabular-nums">
                    {marker.co2Kg != null ? `${marker.co2Kg.toFixed(1)} kg` : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-[10px] font-semibold uppercase text-zinc-500">EBITDA (est.)</dt>
                  <dd className="tabular-nums">
                    {marker.margenOpEstEUR != null
                      ? `${marker.margenOpEstEUR.toLocaleString("es-ES", { maximumFractionDigits: 0 })} €`
                      : "—"}
                  </dd>
                </div>
              </div>
              {marker.matricula ? (
                <p className="text-[11px] text-zinc-600">
                  Vehículo: <span className="font-mono font-medium">{marker.matricula}</span>
                </p>
              ) : null}
            </dl>
          </div>
        </InfoWindow>
      ) : null}
    </>
  );
}

export type FleetIntelligenceMapProps = {
  portes: PorteListRow[];
  vehiclesById: Record<string, FlotaInventarioRow>;
  loadingList?: boolean;
  listError?: string | null;
  className?: string;
};

export function FleetIntelligenceMap({
  portes,
  vehiclesById,
  loadingList = false,
  listError = null,
  className,
}: FleetIntelligenceMapProps) {
  const apiKey =
    process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || process.env.NEXT_PUBLIC_MAPS_API_KEY || "";
  const [geocoding, setGeocoding] = useState(false);
  const [costEurKm, setCostEurKm] = useState(publicOperationalCostEurKmDefault());

  useEffect(() => {
    void getOperationalCostEurKmCached().then(setCostEurKm);
  }, []);

  if (!apiKey) {
    return (
      <div
        className={cn(
          "flex min-h-[min(100dvh,720px)] w-full items-center justify-center border border-amber-500/30 bg-zinc-950 px-4 text-center text-sm text-amber-100",
          className,
        )}
      >
        Define{" "}
        <code className="mx-1 rounded bg-zinc-900 px-1.5 py-0.5 text-xs text-emerald-300/90">
          NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
        </code>{" "}
        (Geocoding + Maps JavaScript API habilitadas en Google Cloud).
      </div>
    );
  }

  if (listError) {
    return (
      <div
        className={cn(
          "flex min-h-[min(100dvh,720px)] w-full items-center justify-center border border-rose-500/30 bg-zinc-950 px-4 text-center text-sm text-rose-200",
          className,
        )}
      >
        {listError}
      </div>
    );
  }

  if (loadingList) {
    return (
      <div
        className={cn(
          "flex min-h-[min(100dvh,720px)] w-full items-center justify-center bg-zinc-950 text-sm text-zinc-400",
          className,
        )}
      >
        Cargando portes activos…
      </div>
    );
  }

  return (
    <div className={cn("relative min-h-[min(100dvh,720px)] w-full bg-zinc-950", className)}>
      <APIProvider apiKey={apiKey} libraries={["marker"]}>
        <Map
          className="h-[100dvh] w-full [&_.map]:!h-full"
          defaultCenter={DEFAULT_CENTER}
          defaultZoom={6}
          gestureHandling="greedy"
          disableDefaultUI={false}
          mapTypeControl={false}
          streetViewControl={false}
          styles={BUNKER_MAP_STYLES}
          colorScheme="DARK"
        >
          <FleetMapInner
            portes={portes}
            vehiclesById={vehiclesById}
            costEurKm={costEurKm}
            onGeocodingChange={setGeocoding}
          />
        </Map>
      </APIProvider>

      <div className="pointer-events-none absolute bottom-6 left-4 right-4 z-10 flex flex-wrap items-end justify-between gap-3">
        <div className="pointer-events-auto max-w-md rounded-xl border border-zinc-800/90 bg-zinc-950/90 px-4 py-3 text-xs text-zinc-400 shadow-xl backdrop-blur">
          <p className="font-semibold uppercase tracking-wide text-zinc-500">Leyenda</p>
          <ul className="mt-2 space-y-1.5">
            <li className="flex items-center gap-2">
              <Star className="h-4 w-4 shrink-0 fill-emerald-400 text-emerald-300" aria-hidden />
              Alta rentabilidad y bajo CO₂ por km
            </li>
            <li className="flex items-center gap-2">
              <span className="inline-flex h-4 w-4 shrink-0 rounded-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.6)]" />
              Euro III / margen bajo
            </li>
            <li className="flex items-center gap-2">
              <span className="inline-flex h-3 w-3 shrink-0 rounded-full bg-emerald-500" />
              Porte activo (estándar)
            </li>
          </ul>
        </div>
        {geocoding ? (
          <div className="pointer-events-auto rounded-lg border border-zinc-700 bg-zinc-900/95 px-3 py-2 text-xs text-zinc-300">
            Geocodificando rutas…
          </div>
        ) : null}
      </div>
    </div>
  );
}
