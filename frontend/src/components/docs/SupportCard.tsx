"use client";

import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Leaf,
  Route,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Truck,
} from "lucide-react";

const PILLARS = [
  {
    title: "Blindaje fiscal (VeriFactu)",
    description:
      "Facturas con trazabilidad AEAT: badge Aceptada, Con errores o Rechazada visible antes del cierre.",
    href: "/facturas",
    icon: ShieldCheck,
    accent: "from-emerald-500/30 to-teal-500/15",
    iconRing: "ring-emerald-500/25",
  },
  {
    title: "Matriz CIP (margen vs CO₂)",
    description:
      "Burbujas por ruta: Estrellas (margen alto, huella contenida) frente a Vampiros (sangría de margen).",
    href: "/dashboard/analitica",
    icon: Route,
    accent: "from-emerald-500/25 to-teal-600/10",
    iconRing: "ring-emerald-500/25",
  },
  {
    title: "Salud de flota",
    description:
      "Alertas ITV, seguro y km; consumo en Combustible para cortar paradas no planificadas.",
    href: "/flota/mantenimiento",
    icon: Truck,
    accent: "from-amber-500/20 to-orange-500/10",
    iconRing: "ring-amber-500/20",
  },
  {
    title: "Simulador de escenarios",
    description:
      "Sliders combustible, salarios y peajes → EBITDA y punto de ruptura tarifario para negociar con cargadores.",
    href: "/dashboard/finanzas/simulador",
    icon: SlidersHorizontal,
    accent: "from-emerald-600/20 to-zinc-900/40",
    iconRing: "ring-emerald-500/20",
  },
] as const;

export function SupportCard() {
  return (
    <section
      aria-labelledby="support-card-heading"
      className="dashboard-bento relative overflow-hidden p-6 sm:p-7"
    >
      <div
        className="pointer-events-none absolute -right-20 -top-24 h-56 w-56 rounded-full bg-gradient-to-br from-emerald-500/10 to-transparent blur-3xl"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute -bottom-16 -left-12 h-48 w-48 rounded-full bg-gradient-to-tr from-emerald-400/5 to-transparent blur-3xl"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-emerald-500/25 to-transparent"
        aria-hidden
      />

      <div className="relative">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-3 sm:gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-600 to-emerald-900 text-white shadow-lg shadow-emerald-900/40 ring-2 ring-emerald-500/20">
              <BookOpen className="h-5 w-5" aria-hidden />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-emerald-400/90">
                Guía rápida · AB Logistics OS
              </p>
              <h2
                id="support-card-heading"
                className="mt-1 text-lg font-semibold tracking-tight text-zinc-100 sm:text-xl"
              >
                Bienvenido al Búnker: control total, ROI medible
              </h2>
              <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-zinc-400">
                Cuatro pilares para blindar la facturación, priorizar rutas rentables, anticipar el taller y
                negociar tarifas con datos. Use los accesos para profundizar en cada área.
              </p>
            </div>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center lg:flex-col lg:items-end">
            <div className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-300">
              <Sparkles className="h-3.5 w-3.5 shrink-0 text-emerald-400" aria-hidden />
              Tip ahorro: revise la Matriz CIP antes del cierre mensual
            </div>
            <div className="inline-flex items-center gap-1.5 rounded-full border border-zinc-800/60 bg-zinc-900/40 px-3 py-1.5 text-xs font-medium text-zinc-400">
              <Leaf className="h-3.5 w-3.5 shrink-0 text-emerald-500/90" aria-hidden />
              ESG + margen en un solo gráfico
            </div>
          </div>
        </div>

        <ul className="mt-6 grid gap-3 sm:grid-cols-2">
          {PILLARS.map((p) => {
            const Icon = p.icon;
            return (
              <li key={p.title}>
                <Link
                  href={p.href}
                  className={`group flex gap-3 rounded-xl border border-zinc-800/50 bg-zinc-900/40 p-4 shadow-none backdrop-blur transition hover:border-emerald-500/30 hover:shadow-[0_0_20px_rgba(16,185,129,0.1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950`}
                >
                  <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${p.accent} text-zinc-100 ring-1 ${p.iconRing}`}
                  >
                    <Icon className="h-5 w-5" aria-hidden />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-zinc-100 group-hover:text-emerald-300">{p.title}</p>
                    <p className="mt-0.5 text-sm leading-snug text-zinc-500">{p.description}</p>
                    <span className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-emerald-400 group-hover:underline">
                      Abrir módulo
                      <ArrowRight
                        className="h-3.5 w-3.5 opacity-80 transition group-hover:translate-x-0.5"
                        aria-hidden
                      />
                    </span>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>

        <p className="mt-5 border-t border-zinc-800/50 pt-4 text-xs text-zinc-500">
          Documentación ejecutiva completa:{" "}
          <code className="rounded bg-zinc-900 px-1.5 py-0.5 font-mono text-[11px] text-zinc-400">
            QUICKSTART_GUIDE.md
          </code>{" "}
          en la raíz del repositorio.
        </p>
      </div>
    </section>
  );
}
