"use client";

import { motion } from "framer-motion";
import { FileCheck2, Lock, Wallet } from "lucide-react";

import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { FadeInSection } from "./FadeInSection";

const icons = [FileCheck2, Lock, Wallet] as const;

export function LandingTrustStrip() {
  const { catalog } = useOptionalLocaleCatalog();
  const l = catalog.landing.trustStrip;

  return (
    <FadeInSection id="trust" className="scroll-mt-24 px-4 py-24 sm:px-6 sm:py-28">
      <div className="mx-auto max-w-6xl">
        <p className="text-xs font-semibold uppercase tracking-widest text-zinc-500">{l.eyebrow}</p>
        <h2 className="mt-2 max-w-3xl text-balance text-2xl font-bold tracking-tight text-white sm:text-3xl">{l.title}</h2>
        <p className="mt-3 max-w-2xl text-pretty text-sm leading-relaxed text-zinc-400 sm:text-base">{l.subtitle}</p>
        <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3">
          {l.bullets.map((b, i) => {
            const Icon = icons[i] ?? icons[0];
            return (
              <motion.article
                key={b.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ duration: 0.5, delay: i * 0.08, ease: [0.25, 0.1, 0.25, 1] }}
                className="flex flex-col rounded-2xl border border-zinc-800 bg-zinc-900/45 p-6"
              >
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-zinc-800 bg-surface-icon text-emerald-500">
                  <Icon className="h-5 w-5" strokeWidth={1.75} aria-hidden />
                </span>
                <h3 className="mt-4 text-lg font-semibold tracking-tight text-white">{b.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">{b.body}</p>
              </motion.article>
            );
          })}
        </div>
      </div>
    </FadeInSection>
  );
}
