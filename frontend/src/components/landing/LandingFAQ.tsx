"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { FadeInSection } from "./FadeInSection";

export function LandingFAQ() {
  const [open, setOpen] = useState<number | null>(0);
  const { catalog } = useOptionalLocaleCatalog();
  const l = catalog.landing.faq;

  return (
    <FadeInSection id="help" className="scroll-mt-20 px-4 py-16 sm:px-6">
      <div className="mx-auto max-w-3xl">
        <div className="text-center mb-10">
          <h2 className="text-2xl font-bold text-white sm:text-3xl">{l.title}</h2>
          <p className="mt-2 text-zinc-400 text-sm">{l.subtitle}</p>
        </div>
        <div className="space-y-3">
          {l.items.map((item, i) => {
            const isOpen = open === i;
            return (
              <div
                key={item.q}
                className="rounded-2xl border border-zinc-800 bg-zinc-900/50 overflow-hidden"
              >
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left text-sm font-semibold text-white hover:bg-zinc-800/50 transition"
                  onClick={() => setOpen(isOpen ? null : i)}
                  aria-expanded={isOpen}
                >
                  {item.q}
                  <ChevronDown
                    className={`h-5 w-5 shrink-0 text-zinc-500 transition-transform ${isOpen ? "rotate-180" : ""}`}
                  />
                </button>
                {isOpen && (
                  <div className="px-5 pb-4 text-sm text-zinc-400 leading-relaxed border-t border-zinc-800/80 pt-3">
                    {item.a}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </FadeInSection>
  );
}
