"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";

const fadeUp = {
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0 },
};

export function LandingMarketingHero() {
  const { catalog } = useOptionalLocaleCatalog();
  const l = catalog.landing.hero;

  return (
    <section className="relative overflow-hidden px-4 pb-24 pt-16 sm:px-6 sm:pb-32 sm:pt-24">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(16,185,129,0.12),transparent)]" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(39,39,42,0.4),transparent_50%)]" />
      <div className="relative mx-auto max-w-6xl">
        <motion.p
          className="text-xs font-semibold uppercase tracking-widest text-zinc-400"
          variants={fadeUp}
          initial="initial"
          animate="animate"
          transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
        >
          {l.eyebrow}
        </motion.p>
        <motion.h1
          className="mt-5 max-w-4xl text-balance text-3xl font-extrabold tracking-tight text-white sm:text-5xl lg:text-[3.25rem] lg:leading-[1.1]"
          variants={fadeUp}
          initial="initial"
          animate="animate"
          transition={{ duration: 0.55, delay: 0.06, ease: [0.25, 0.1, 0.25, 1] }}
        >
          {l.title}
        </motion.h1>
        <motion.p
          className="mt-6 max-w-3xl text-pretty text-base leading-relaxed text-zinc-300 sm:text-lg"
          variants={fadeUp}
          initial="initial"
          animate="animate"
          transition={{ duration: 0.55, delay: 0.12, ease: [0.25, 0.1, 0.25, 1] }}
        >
          {l.description}
        </motion.p>
        <motion.div
          className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4"
          variants={fadeUp}
          initial="initial"
          animate="animate"
          transition={{ duration: 0.55, delay: 0.18, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <Link
            href="/login"
            className="inline-flex min-h-11 items-center justify-center rounded-full bg-emerald-500 px-8 py-3 text-sm font-semibold text-zinc-950 shadow-lg shadow-emerald-500/20 transition hover:bg-emerald-400"
          >
            {l.primaryCta}
          </Link>
          <Link
            href="#plataforma"
            className="inline-flex min-h-11 items-center justify-center rounded-full border border-zinc-700 bg-transparent px-8 py-3 text-sm font-semibold text-zinc-300 transition hover:border-zinc-600 hover:bg-zinc-900/50 hover:text-white"
          >
            {l.secondaryCta}
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
