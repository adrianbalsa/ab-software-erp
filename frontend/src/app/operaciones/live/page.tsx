"use client";

import { ChevronLeft, ChevronRight, MapPin, Radio } from "lucide-react";
import { useCallback, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { LiveFleetMap } from "@/components/maps/LiveFleetMap";
import { useLiveFleet } from "@/hooks/useLiveFleet";
import type { LiveFleetVehicle } from "@/lib/api";

function estadoBadgeClass(estado: LiveFleetVehicle["estado"]): string {
  if (estado === "En Ruta") return "bg-blue-500/20 text-blue-200 border-blue-500/40";
  if (estado === "Taller") return "bg-red-500/20 text-red-200 border-red-500/40";
  return "bg-emerald-500/20 text-emerald-200 border-emerald-500/40";
}

export default function OperacionesLivePage() {
  const { vehicles, loading, error, refresh } = useLiveFleet();
  const [panelOpen, setPanelOpen] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<string | null>(null);

  const onListPick = useCallback((id: string) => {
    setSelectedId(id);
    setFocusId(id);
  }, []);

  return (
    <RoleGuard
      allowedRoles={["owner", "traffic_manager"]}
      fallback={
        <AppShell active="dashboard">
          <main className="flex flex-1 items-center justify-center p-8">
            <p className="rounded-xl border border-amber-800/60 bg-amber-950/40 px-6 py-4 text-sm text-amber-100">
              El centro de mando solo está disponible para propietarios y traffic managers.
            </p>
          </main>
        </AppShell>
      }
    >
      <AppShell active="operaciones">
        <div className="flex min-h-0 flex-1 flex-col bg-[#0a0e18] text-zinc-100">
          <header className="flex h-14 shrink-0 items-center justify-between border-b border-zinc-800/90 px-4 md:px-6">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-400">
                <Radio className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-lg font-bold tracking-tight text-white">Centro de mando</h1>
                <p className="text-xs text-zinc-500">Flota en vivo · actualización cada 15 s</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => void refresh()}
              className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-zinc-200 hover:bg-zinc-800"
            >
              Actualizar ahora
            </button>
          </header>

          <div className="flex min-h-0 min-h-[min(100dvh,720px)] flex-1 md:min-h-[calc(100dvh-3.5rem)]">
            <aside
              className={`relative flex shrink-0 flex-col border-r border-zinc-800 bg-zinc-950/90 transition-[width] duration-200 ease-out ${
                panelOpen ? "w-[min(100%,320px)]" : "w-12"
              }`}
            >
              <button
                type="button"
                aria-expanded={panelOpen}
                onClick={() => setPanelOpen((o) => !o)}
                className="absolute -right-3 top-3 z-10 flex h-7 w-7 items-center justify-center rounded-full border border-zinc-600 bg-zinc-900 text-zinc-300 shadow-lg hover:bg-zinc-800"
              >
                {panelOpen ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>

              {panelOpen ? (
                <>
                  <div className="border-b border-zinc-800 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
                      Vehículos ({vehicles.length})
                    </p>
                  </div>
                  <div className="flex-1 overflow-y-auto p-2">
                    {vehicles.length === 0 && !loading ? (
                      <p className="px-2 py-4 text-sm text-zinc-500">No hay vehículos en inventario operativo.</p>
                    ) : (
                      <ul className="space-y-1">
                        {vehicles.map((v) => {
                          const hasPos =
                            v.ultima_latitud != null &&
                            v.ultima_longitud != null &&
                            !Number.isNaN(v.ultima_latitud) &&
                            !Number.isNaN(v.ultima_longitud);
                          const active = selectedId === v.id;
                          return (
                            <li key={v.id}>
                              <button
                                type="button"
                                onClick={() => onListPick(v.id)}
                                className={`flex w-full flex-col rounded-xl border px-3 py-2.5 text-left transition-colors ${
                                  active
                                    ? "border-emerald-500/50 bg-emerald-500/10"
                                    : "border-zinc-800 bg-zinc-900/50 hover:border-zinc-700"
                                }`}
                              >
                                <div className="flex items-center justify-between gap-2">
                                  <span className="font-mono text-sm font-semibold text-white">{v.matricula}</span>
                                  <span
                                    className={`rounded-md border px-1.5 py-0.5 text-[10px] font-bold uppercase ${estadoBadgeClass(v.estado)}`}
                                  >
                                    {v.estado}
                                  </span>
                                </div>
                                <p className="mt-1 truncate text-xs text-zinc-400">
                                  {v.conductor_nombre || "Sin conductor asignado"}
                                </p>
                                {!hasPos && (
                                  <p className="mt-1 text-[11px] text-amber-500/90">Sin coordenadas GPS</p>
                                )}
                              </button>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                </>
              ) : (
                <div className="flex flex-1 flex-col items-center pt-14 text-zinc-600">
                  <MapPin className="h-5 w-5" />
                </div>
              )}
            </aside>

            <div className="relative h-full min-h-[420px] min-w-0 flex-1">
              <LiveFleetMap
                vehicles={vehicles}
                focusVehicleId={focusId}
                selectedVehicleId={selectedId}
                onSelectVehicle={setSelectedId}
                loading={loading}
                error={error}
              />
            </div>
          </div>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
