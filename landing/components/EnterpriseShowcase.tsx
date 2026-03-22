"use client";

import { motion } from "framer-motion";
import {
  BarChart3,
  Leaf,
  MessageSquare,
  Sparkles,
  TrendingUp,
  Truck,
} from "lucide-react";

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, delay: i * 0.08, ease: [0.25, 0.1, 0.25, 1] as const },
  }),
};

export function EnterpriseShowcase() {
  return (
    <section id="producto" className="relative border-y border-zinc-200/80 bg-[#f4f6fb] py-20">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(16,185,129,0.08),transparent)]" />
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <motion.div
          variants={fadeUp}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          custom={0}
          className="mb-12 text-center"
        >
          <span className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            Plataforma en vivo
          </span>
          <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-zinc-900 sm:text-4xl">
            El mismo producto que verás al iniciar sesión
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-zinc-600 sm:text-base">
            Paneles financieros, certificación ambiental y asistente económico — unificados en una experiencia enterprise,
            no un mockup de marketing desconectado.
          </p>
        </motion.div>

        <div className="grid gap-6 lg:grid-cols-12 lg:items-stretch">
          {/* Dashboard financiero — Margen/km */}
          <motion.div
            variants={fadeUp}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            custom={1}
            className="lg:col-span-7"
          >
            <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-zinc-200/90 bg-white shadow-[0_1px_3px_rgba(15,23,42,0.06),0_20px_50px_-12px_rgba(15,23,42,0.12)]">
              <div className="flex items-center justify-between border-b border-zinc-100 bg-zinc-50/80 px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="flex gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-red-400/90" />
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-400/90" />
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/90" />
                  </span>
                  <span className="text-xs font-medium text-zinc-500">AB Logistics OS</span>
                </div>
                <span className="rounded-md bg-white px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400 ring-1 ring-zinc-200/80">
                  Finanzas
                </span>
              </div>
              <div className="flex min-h-[280px] flex-1">
                <div className="hidden w-14 shrink-0 flex-col border-r border-zinc-100 bg-gradient-to-b from-zinc-900 to-zinc-950 sm:flex">
                  <div className="flex h-10 items-center justify-center border-b border-white/10">
                    <Truck className="h-4 w-4 text-emerald-400/90" />
                  </div>
                  <div className="flex flex-1 flex-col gap-2 p-2">
                    <div className="h-7 rounded-lg bg-white/10" />
                    <div className="h-7 rounded-lg bg-white/5" />
                    <div className="h-7 rounded-lg bg-white/5" />
                  </div>
                </div>
                <div className="flex flex-1 flex-col gap-4 p-4 sm:p-5">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                      Rentabilidad por distancia
                    </p>
                    <p className="mt-1 text-lg font-bold tracking-tight text-zinc-900">Dashboard financiero</p>
                  </div>
                  <div className="grid grid-cols-3 gap-2 sm:gap-3">
                    <div className="rounded-xl border border-zinc-100 bg-zinc-50/80 p-3">
                      <p className="text-[10px] font-medium uppercase text-zinc-400">Ingreso/km</p>
                      <p className="mt-1 text-lg font-bold tabular-nums text-zinc-800">1,28 €</p>
                    </div>
                    <div className="rounded-xl border border-zinc-100 bg-zinc-50/80 p-3">
                      <p className="text-[10px] font-medium uppercase text-zinc-400">Coste/km</p>
                      <p className="mt-1 text-lg font-bold tabular-nums text-zinc-800">0,86 €</p>
                    </div>
                    <div className="rounded-xl border border-emerald-200/80 bg-gradient-to-br from-emerald-50 to-white p-3 ring-1 ring-emerald-500/15">
                      <p className="text-[10px] font-semibold uppercase text-emerald-700/90">Margen/km</p>
                      <p className="mt-1 flex items-baseline gap-1 text-lg font-black tabular-nums text-emerald-700">
                        0,42 €
                        <TrendingUp className="inline h-3.5 w-3.5 text-emerald-600" aria-hidden />
                      </p>
                    </div>
                  </div>
                  <div className="mt-auto rounded-xl border border-zinc-100 bg-zinc-50/50 p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
                        Margen acumulado (7d)
                      </span>
                      <BarChart3 className="h-3.5 w-3.5 text-zinc-300" aria-hidden />
                    </div>
                    <div className="flex h-16 items-end gap-1.5">
                      {[40, 55, 48, 72, 65, 78, 85].map((h, i) => (
                        <div
                          key={i}
                          className="flex-1 rounded-t-md bg-gradient-to-t from-zinc-300 to-zinc-400/90"
                          style={{ height: `${h}%` }}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

          <div className="flex flex-col gap-6 lg:col-span-5">
            {/* Certificado ESG / CO2 */}
            <motion.div
              variants={fadeUp}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true }}
              custom={2}
              className="flex flex-1 flex-col overflow-hidden rounded-2xl border border-emerald-200/70 bg-gradient-to-br from-emerald-50/90 via-white to-zinc-50 shadow-[0_1px_3px_rgba(15,23,42,0.06)]"
            >
              <div className="flex items-start justify-between gap-3 border-b border-emerald-100/80 bg-white/60 px-4 py-3 backdrop-blur-sm">
                <div className="flex items-center gap-2">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-md shadow-emerald-900/20">
                    <Leaf className="h-4 w-4" aria-hidden />
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-800/80">
                      Certificado ESG
                    </p>
                    <p className="text-sm font-bold text-zinc-900">Huella operativa</p>
                  </div>
                </div>
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                  LIVE
                </span>
              </div>
              <div className="flex flex-1 flex-col justify-center gap-3 px-4 py-4">
                <p className="text-xs leading-relaxed text-zinc-600">
                  CO₂ calculado con factor de referencia Euro VI y distancia real de ruta (no estimación genérica).
                </p>
                <div className="rounded-xl border border-emerald-200/60 bg-white/90 p-4 shadow-sm">
                  <p className="text-[10px] font-medium uppercase text-zinc-400">CO₂ atribuible (periodo)</p>
                  <p className="mt-1 text-3xl font-black tabular-nums tracking-tight text-emerald-700">
                    2.847{" "}
                    <span className="text-lg font-bold text-emerald-600/90">kg</span>
                  </p>
                  <p className="mt-2 text-[11px] text-zinc-500">Equivale a evitar ~1.420 km en vehículo particular medio.</p>
                </div>
              </div>
            </motion.div>

            {/* LogisAdvisor chat */}
            <motion.div
              variants={fadeUp}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true }}
              custom={3}
              className="flex flex-1 flex-col overflow-hidden rounded-2xl border border-zinc-200/90 bg-white shadow-[0_1px_3px_rgba(15,23,42,0.06)]"
            >
              <div className="flex items-center gap-2 border-b border-zinc-100 bg-zinc-50/90 px-4 py-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-zinc-700 to-emerald-600 text-white">
                  <Sparkles className="h-4 w-4" aria-hidden />
                </div>
                <div>
                  <p className="text-xs font-bold text-zinc-900">LogisAdvisor</p>
                  <p className="text-[10px] text-zinc-500">Asistente económico · confidencial</p>
                </div>
                <MessageSquare className="ml-auto h-4 w-4 text-zinc-300" aria-hidden />
              </div>
              <div className="space-y-3 p-4">
                <div className="ml-auto max-w-[92%] rounded-2xl rounded-tr-md bg-zinc-100 px-3 py-2.5 text-xs leading-relaxed text-zinc-800">
                  ¿A qué precio mínimo debo cotizar un porte de 640 km para mantener un margen bruto del 18% con mi
                  coste variable actual?
                </div>
                <div className="max-w-[95%] rounded-2xl rounded-tl-md border border-emerald-100 bg-emerald-50/80 px-3 py-2.5 text-xs leading-relaxed text-zinc-800">
                  <p className="mb-2 font-semibold text-emerald-900">Respuesta sugerida</p>
                  <p className="text-zinc-700">
                    Con tu <strong>coste/km</strong> cargado (combustible + peajes + amortización), el piso recomendado es{" "}
                    <strong className="text-emerald-800">1,52 €/km</strong> para ese objetivo de margen. Si el shipper
                    negocia por debajo, activa alerta de <em>viaje a pérdidas</em> en el simulador.
                  </p>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}
