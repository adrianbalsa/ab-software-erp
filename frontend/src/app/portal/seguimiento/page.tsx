"use client";

import dynamic from "next/dynamic";
import Link from "next/link";

const PortalSeguimientoMapClient = dynamic(
  () => import("@/components/maps/PortalSeguimientoMapClient"),
  { ssr: false, loading: () => <p className="text-sm text-zinc-500">Preparando mapa…</p> },
);

export default function PortalSeguimientoPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Seguimiento logístico</h1>
          <p className="mt-1 text-sm text-zinc-600">
            Marcadores de entregas recientes (geostamps de destino). Los datos provienen de su cuenta
            autenticada en la API.
          </p>
        </div>
        <Link
          href="/portal-cliente/mis-portes"
          className="text-sm font-medium text-blue-700 hover:text-blue-600 hover:underline"
        >
          Volver a mis portes
        </Link>
      </div>
      <PortalSeguimientoMapClient />
    </div>
  );
}
