"use client";

import { BarChart3, Globe2, Shield } from "lucide-react";

import { FadeInSection } from "./FadeInSection";

export function LandingMoats() {
  return (
    <FadeInSection id="moats" className="scroll-mt-24 px-4 py-16 sm:px-6 bg-zinc-950/50">
      <div className="mx-auto max-w-6xl">
        <div className="text-center mb-12 max-w-2xl mx-auto">
          <h2 className="text-2xl font-bold text-white sm:text-3xl">Por qué AB Logistics OS</h2>
          <p className="mt-2 text-zinc-400 text-sm sm:text-base">
            Tres pilares que blindan tu negocio frente a normativa, competencia y licitaciones.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3 lg:grid-rows-2 lg:gap-5 min-h-[420px]">
          <article className="lg:col-span-2 lg:row-span-2 rounded-3xl border border-zinc-800 bg-gradient-to-br from-zinc-900 via-zinc-900 to-blue-950/40 p-8 flex flex-col justify-between shadow-xl">
            <div>
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-500/20 text-blue-400 mb-6">
                <Shield className="h-6 w-6" />
              </div>
              <h3 className="text-xl font-bold text-white sm:text-2xl">Blindaje VeriFactu</h3>
              <p className="mt-4 text-zinc-400 leading-relaxed text-sm sm:text-base max-w-xl">
                Inmutabilidad criptográfica de cada factura y cadena de hashes trazable. Reduce el riesgo de
                sanciones: las multas por incumplimiento pueden superar los{" "}
                <span className="text-white font-semibold">50.000 €</span>. Tu expediente queda defendible ante
                inspección AEAT.
              </p>
            </div>
            <p className="mt-8 text-xs text-zinc-500 uppercase tracking-wider">Legal · Cumplimiento 2026</p>
          </article>

          <article className="rounded-3xl border border-zinc-800 bg-zinc-900/80 p-6 lg:row-start-1 lg:col-start-3 shadow-lg">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-400 mb-4">
              <BarChart3 className="h-5 w-5" />
            </div>
            <h3 className="text-lg font-bold text-white">Math Engine (EBITDA real)</h3>
            <p className="mt-3 text-sm text-zinc-400 leading-relaxed">
              Deja de adivinar: cruza gasoil, desgaste, facturación y portes para conocer el{" "}
              <span className="text-emerald-400/90">margen exacto</span> de cada ruta y de tu operación.
            </p>
          </article>

          <article className="rounded-3xl border border-zinc-800 bg-zinc-900/80 p-6 lg:row-start-2 lg:col-start-3 shadow-lg">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600/15 text-emerald-400 mb-4">
              <Globe2 className="h-5 w-5" />
            </div>
            <h3 className="text-lg font-bold text-white">Certificación ESG</h3>
            <p className="mt-3 text-sm text-zinc-400 leading-relaxed">
              Reportes de emisiones automáticos para acceder a licitaciones de grandes multinacionales que exigen
              trazabilidad de huella de carbono.
            </p>
          </article>
        </div>
      </div>
    </FadeInSection>
  );
}
