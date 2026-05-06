"use client";

import { motion } from "framer-motion";

import { useOptionalLocaleCatalog } from "@/context/LocaleContext";

export function LandingSocialProof() {
  const { catalog } = useOptionalLocaleCatalog();
  const l = catalog.landing.socialProof;

  return (
    <section
      aria-labelledby="social-proof-heading"
      className="border-y border-zinc-200/70 dark:border-zinc-800/60 bg-gradient-to-b from-zinc-100/90 dark:from-zinc-950/80 to-zinc-50 dark:to-zinc-950 px-4 py-16 sm:px-6 sm:py-20"
    >
      <div className="mx-auto max-w-6xl">
        <p className="text-xs font-semibold uppercase tracking-widest text-emerald-500/90">{l.eyebrow}</p>
        <h2
          id="social-proof-heading"
          className="mt-2 max-w-3xl text-balance text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 sm:text-3xl"
        >
          {l.title}
        </h2>
        <p className="mt-3 max-w-2xl text-pretty text-sm leading-relaxed text-zinc-600 dark:text-zinc-400 sm:text-base">{l.subtitle}</p>
        <div className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-3">
          {l.stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-24px" }}
              transition={{ duration: 0.45, delay: i * 0.06, ease: [0.25, 0.1, 0.25, 1] }}
              className="rounded-2xl border border-zinc-200/90 dark:border-zinc-800/90 bg-zinc-50/95 dark:bg-zinc-900/40 p-6"
            >
              <p className="text-2xl font-bold tracking-tight text-emerald-400">{stat.value}</p>
              <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{stat.label}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
