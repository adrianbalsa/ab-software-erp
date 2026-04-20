"use client";

import dynamic from "next/dynamic";
import Link from "next/link";

const AdminHeatmapMapClient = dynamic(
  () => import("@/components/maps/AdminHeatmapMapClient"),
  { ssr: false, loading: () => <p className="text-sm text-zinc-400">Preparando mapa de calor…</p> },
);

export default function AdminDashboardMapPage() {
  return (
    <div className="min-h-screen bg-zinc-950 px-4 py-8 text-zinc-100">
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Mapa de calor (actividad)</h1>
            <p className="mt-1 text-sm text-zinc-400">
              Requiere sesión con permisos de administración / explotación. Agregación por celdas con
              tooltips de ticket medio de gastos por zona.
            </p>
          </div>
          <Link
            href="/admin"
            className="text-sm font-medium text-emerald-400 hover:text-emerald-300 hover:underline"
          >
            Volver al panel admin
          </Link>
        </div>
        <AdminHeatmapMapClient />
      </div>
    </div>
  );
}
