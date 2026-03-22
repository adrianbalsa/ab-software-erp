"use client";

import Link from "next/link";
import { Check } from "lucide-react";

import { FadeInSection } from "./FadeInSection";

const tiers = [
  {
    name: "Starter",
    price: "19",
    desc: "Ideal para autónomos y pequeñas flotas.",
    features: ["Hasta 5 vehículos", "VeriFactu full", "Cumplimiento AEAT 2026"],
    highlight: false,
  },
  {
    name: "Pro",
    price: "89",
    desc: "Operación en crecimiento con control financiero real.",
    features: ["Hasta 25 vehículos", "Math Engine activo", "Conciliación y reporting"],
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "249",
    desc: "Grandes flotas y licitaciones internacionales.",
    features: ["Flota ilimitada", "Módulo ESG completo", "Exportación avanzada AEAT"],
    highlight: false,
  },
];

export function LandingPricing() {
  return (
    <FadeInSection id="pricing" className="scroll-mt-24 px-4 py-16 sm:px-6 bg-zinc-950/40">
      <div className="mx-auto max-w-6xl">
        <div className="text-center mb-12">
          <h2 className="text-2xl font-bold text-white sm:text-3xl">Precios claros</h2>
          <p className="mt-2 text-zinc-400 text-sm sm:text-base">
            Tres planes. Sin sorpresas. Empieza cuando quieras.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {tiers.map((tier) => (
            <div
              key={tier.name}
              className={`relative flex flex-col rounded-3xl border p-8 ${
                tier.highlight
                  ? "border-emerald-400/60 bg-gradient-to-b from-emerald-500/10 to-zinc-900/90 shadow-2xl shadow-emerald-500/10 ring-2 ring-emerald-500/30 md:-translate-y-1 md:scale-[1.02]"
                  : "border-zinc-800 bg-zinc-900/60"
              }`}
            >
              {tier.highlight && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-emerald-500 px-3 py-0.5 text-xs font-bold uppercase tracking-wide text-zinc-950">
                  Recomendado
                </span>
              )}
              <h3 className="text-lg font-bold text-white">{tier.name}</h3>
              <p className="mt-2 text-sm text-zinc-500">{tier.desc}</p>
              <div className="mt-6 flex items-baseline gap-1">
                <span className="text-4xl font-extrabold text-white">{tier.price}€</span>
                <span className="text-zinc-500">/mes</span>
              </div>
              <ul className="mt-8 flex-1 space-y-3 text-sm text-zinc-300">
                {tier.features.map((f) => (
                  <li key={f} className="flex items-start gap-2">
                    <Check className="h-4 w-4 shrink-0 text-emerald-500 mt-0.5" />
                    {f}
                  </li>
                ))}
              </ul>
              <Link
                href="/login"
                className={`mt-8 block w-full rounded-full py-3 text-center text-sm font-semibold transition ${
                  tier.highlight
                    ? "bg-emerald-500 text-zinc-950 hover:bg-emerald-400"
                    : "border border-zinc-600 text-zinc-200 hover:bg-zinc-800"
                }`}
              >
                Empezar prueba gratuita
              </Link>
            </div>
          ))}
        </div>
      </div>
    </FadeInSection>
  );
}
