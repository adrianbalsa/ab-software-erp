"use client";

import Image from "next/image";
import Link from "next/link";

const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, "") || "https://app.ablogistics-os.com";

/**
 * Vista pública ligera cuando el build del ERP se sirve bajo el dominio raíz
 * (p. ej. preview o proxy mal configurado). El despliegue Docker suele servir
 * el contenedor `landing` en ablogistics-os.com; este componente evita mostrar login aquí.
 */
export function RootDomainLanding() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white text-slate-900">
      <header className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-6">
        <div className="flex items-center gap-3">
          <Image
            src="/logo.png"
            alt="AB Logistics OS"
            width={48}
            height={48}
            className="rounded-xl object-contain"
            priority
          />
          <span className="text-lg font-semibold tracking-tight">AB Logistics OS</span>
        </div>
        <Link
          href={APP_URL}
          className="rounded-xl bg-zinc-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-zinc-800"
        >
          Entrar al ERP
        </Link>
      </header>

      <main className="mx-auto max-w-5xl px-6 pb-20 pt-8">
        <h1 className="text-balance text-4xl font-bold tracking-tight text-slate-900 md:text-5xl">
          Operativa, finanzas y cumplimiento en una sola plataforma
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-slate-600">
          Gestión de transporte con VeriFactu, flota, tesorería y portal del conductor. Accede al
          entorno de trabajo desde el subdominio dedicado.
        </p>
        <div className="mt-10">
          <Link
            href={APP_URL}
            className="inline-flex items-center justify-center rounded-xl bg-emerald-600 px-6 py-3 font-semibold text-white shadow-md transition hover:bg-emerald-500"
          >
            Ir a la aplicación
          </Link>
        </div>
      </main>
    </div>
  );
}
