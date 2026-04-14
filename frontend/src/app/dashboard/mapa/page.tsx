"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { FleetIntelligenceMap } from "@/components/maps/FleetIntelligenceMap";
import { api, type FlotaInventarioRow, type PorteListRow } from "@/lib/api";

function MapaContent() {
  const [portes, setPortes] = useState<PorteListRow[]>([]);
  const [inventario, setInventario] = useState<FlotaInventarioRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const vehiclesById = useMemo(() => {
    return Object.fromEntries(inventario.map((v) => [v.id, v]));
  }, [inventario]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const p = await api.portes.list();
      setPortes(Array.isArray(p) ? p : []);
      try {
        const inv = await api.flota.inventario();
        setInventario(Array.isArray(inv) ? inv : []);
      } catch {
        /* inventario exige owner/traffic_manager en API; admin u otros roles siguen viendo portes */
        setInventario([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudieron cargar los datos del mapa.");
      setPortes([]);
      setInventario([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="relative flex min-h-0 min-w-0 flex-1 flex-col">
      <header className="pointer-events-none absolute left-0 right-0 top-0 z-20 flex flex-wrap items-start justify-between gap-3 px-4 pt-4 md:px-6">
        <div className="pointer-events-auto max-w-xl rounded-xl border border-zinc-800/90 bg-zinc-950/90 px-4 py-3 shadow-xl backdrop-blur">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-500">Flota · GIS</p>
          <h1 className="mt-1 font-serif text-xl font-semibold tracking-tight text-zinc-50 md:text-2xl">
            Mapa de inteligencia
          </h1>
          <p className="mt-1 text-xs leading-relaxed text-zinc-500">
            Portes pendientes georreferenciados. Marcadores según rentabilidad estimada, CO₂ y normativa Euro del
            vehículo asignado.
          </p>
        </div>
      </header>

      <FleetIntelligenceMap
        portes={portes}
        vehiclesById={vehiclesById}
        loadingList={loading}
        listError={error}
        className="min-h-0 flex-1"
      />
    </div>
  );
}

export default function MapaPage() {
  return (
    <AppShell active="mapa">
      <RoleGuard
        allowedRoles={["owner", "admin", "traffic_manager"]}
        fallback={
          <main className="bg-zinc-950 p-8">
            <p className="text-sm text-zinc-500">No tienes permiso para ver el mapa operativo.</p>
          </main>
        }
      >
        <MapaContent />
      </RoleGuard>
    </AppShell>
  );
}
