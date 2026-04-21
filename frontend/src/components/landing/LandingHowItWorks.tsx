"use client";

import { FileText, Route, Truck } from "lucide-react";

import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { FadeInSection } from "./FadeInSection";

export function LandingHowItWorks() {
  const { catalog } = useOptionalLocaleCatalog();
  const l = catalog.landing.howItWorks;
  const icons = [Truck, Route, FileText] as const;
  const steps = l.steps.map((step, idx) => ({
    ...step,
    icon: icons[idx] ?? icons[0],
  }));

  return (
    <FadeInSection id="how-it-works" className="scroll-mt-24 px-4 py-24 sm:px-6 sm:py-28">
      <div className="mx-auto max-w-5xl">
        <div className="text-center mb-12">
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">{l.title}</h2>
          <p className="mt-2 text-zinc-300 text-sm sm:text-base">{l.subtitle}</p>
        </div>

        <div className="relative">
          <div className="absolute left-1/2 top-0 bottom-0 hidden md:block w-px bg-gradient-to-b from-blue-500/50 via-emerald-500/30 to-transparent -translate-x-1/2" />
          <div className="space-y-10 md:space-y-0 md:grid md:grid-cols-3 md:gap-8">
            {steps.map((step, i) => (
              <div
                key={step.title}
                className="relative flex flex-col items-center text-center md:pt-0"
              >
                <div className="relative z-10 flex h-14 w-14 items-center justify-center rounded-2xl border border-zinc-700 bg-zinc-900 text-blue-400 shadow-lg shadow-blue-500/10">
                  <step.icon className="h-7 w-7" />
                </div>
                <span className="mt-4 text-xs font-semibold uppercase tracking-widest text-emerald-500/90">
                  {l.stepLabel} {i + 1} · {step.time}
                </span>
                <h3 className="mt-2 text-lg font-bold tracking-tight text-white">{step.title}</h3>
                <p className="mt-2 text-sm text-zinc-300 leading-relaxed max-w-xs">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </FadeInSection>
  );
}
