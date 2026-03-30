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
    accent: "from-emerald-500/20 to-teal-500/10",
    ring: "ring-emerald-500/20",
  },
  {
    title: "Matriz CIP (margen vs CO₂)",
    description:
      "Burbujas por ruta: Estrellas (margen alto, huella contenida) frente a Vampiros (sangría de margen).",
    href: "/dashboard/analitica",
    icon: Route,
    accent: "from-sky-500/20 to-blue-500/10",
    ring: "ring-sky-500/20",
  },
  {
    title: "Salud de flota",
    description:
      "Alertas ITV, seguro y km; consumo en Combustible para cortar paradas no planificadas.",
    href: "/flota/mantenimiento",
    icon: Truck,
    accent: "from-amber-500/20 to-orange-500/10",
    ring: "ring-amber-500/20",
  },
  {
    title: "Simulador de escenarios",
    description:
      "Sliders combustible, salarios y peajes → EBITDA y punto de ruptura tarifario para negociar con cargadores.",
    href: "/dashboard/finanzas/simulador",
    icon: SlidersHorizontal,
    accent: "from-violet-500/20 to-indigo-500/10",
    ring: "ring-violet-500/20",
  },
] as const;

export function SupportCard() {
  return (
    <section
      aria-labelledby="support-card-heading"
      className="relative overflow-hidden rounded-2xl border border-slate-200/90 bg-gradient-to-br from-slate-50 via-white to-blue-50/50 shadow-md shadow-slate-200/40"
    >
      <div
        className="pointer-events-none absolute -right-20 -top-24 h-56 w-56 rounded-full bg-gradient-to-br from-blue-400/20 to-indigo-400/5 blur-3xl"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute -bottom-16 -left-12 h-48 w-48 rounded-full bg-gradient-to-tr from-emerald-400/15 to-transparent blur-3xl"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-blue-400/35 to-transparent"
        aria-hidden
      />

      <div className="relative p-6 sm:p-7">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-3 sm:gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-800 text-white shadow-lg shadow-blue-600/30 ring-2 ring-white/50">
              <BookOpen className="h-5 w-5" aria-hidden />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-blue-700/90">
                Guía rápida · AB Logistics OS
              </p>
              <h2
                id="support-card-heading"
                className="mt-1 text-lg font-bold tracking-tight text-slate-900 sm:text-xl"
              >
                Bienvenido al Búnker: control total, ROI medible
              </h2>
              <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-slate-600">
                Cuatro pilares para blindar la facturación, priorizar rutas rentables, anticipar el taller y
                negociar tarifas con datos. Use los accesos para profundizar en cada área.
              </p>
            </div>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center lg:flex-col lg:items-end">
            <div className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200/90 bg-emerald-50/95 px-3 py-1.5 text-xs font-semibold text-emerald-950 shadow-sm">
              <Sparkles className="h-3.5 w-3.5 shrink-0 text-emerald-600" aria-hidden />
              Tip ahorro: revise la Matriz CIP antes del cierre mensual
            </div>
            <div className="inline-flex items-center gap-1.5 rounded-full border border-slate-200/90 bg-white/90 px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm">
              <Leaf className="h-3.5 w-3.5 shrink-0 text-emerald-600" aria-hidden />
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
                  className={`group flex gap-3 rounded-xl border border-slate-200/80 bg-white/90 p-4 shadow-sm ring-1 ${p.ring} transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2`}
                >
                  <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${p.accent} text-slate-800 ring-1 ring-slate-200/50`}
                  >
                    <Icon className="h-5 w-5" aria-hidden />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-slate-900 group-hover:text-blue-800">{p.title}</p>
                    <p className="mt-0.5 text-sm leading-snug text-slate-600">{p.description}</p>
                    <span className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-blue-600 group-hover:underline">
                      Abrir módulo
                      <ArrowRight className="h-3.5 w-3.5 opacity-80 transition group-hover:translate-x-0.5" aria-hidden />
                    </span>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>

        <p className="mt-5 border-t border-slate-200/80 pt-4 text-xs text-slate-500">
          Documentación ejecutiva completa:{" "}
          <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700">
            QUICKSTART_GUIDE.md
          </code>{" "}
          en la raíz del repositorio.
        </p>
      </div>
    </section>
  );
}
