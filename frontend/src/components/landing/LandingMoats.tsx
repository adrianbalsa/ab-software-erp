"use client";

import { BarChart3, Calculator, ClipboardCheck, ReceiptText, ShieldCheck, UserRoundCheck } from "lucide-react";

import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { FadeInSection } from "./FadeInSection";

export function LandingMoats() {
  const { catalog } = useOptionalLocaleCatalog();
  const l = catalog.landing.moats;
  const icons = [ShieldCheck, BarChart3, UserRoundCheck, Calculator, ClipboardCheck, ReceiptText] as const;
  const capabilities = l.capabilities.map((capability, idx) => ({
    ...capability,
    icon: icons[idx] ?? icons[0],
  }));

  return (
    <FadeInSection id="moats" className="scroll-mt-24 px-4 py-16 sm:px-6 bg-zinc-950/50">
      <div className="mx-auto max-w-6xl">
        <div className="text-center mb-12 max-w-2xl mx-auto">
          <h2 className="text-2xl font-bold text-white sm:text-3xl">{l.title}</h2>
          <p className="mt-2 text-zinc-400 text-sm sm:text-base">{l.subtitle}</p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 lg:gap-5">
          {capabilities.map((capability) => {
            const Icon = capability.icon;
            return (
              <article
                key={capability.title}
                className="rounded-3xl border border-zinc-800 bg-zinc-900/75 p-6 shadow-lg transition hover:border-zinc-700 hover:bg-zinc-900"
              >
                <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-400 mb-4">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="text-lg font-bold text-white">{capability.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-zinc-400">{capability.description}</p>
              </article>
            );
          })}
        </div>
      </div>
    </FadeInSection>
  );
}
