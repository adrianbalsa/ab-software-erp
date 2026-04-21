"use client";

import { motion } from "framer-motion";

const specs = [
  "Zero-Any Types",
  "Zod Validated",
  "RLS PostgreSQL",
  "AES-128 Encrypted",
] as const;

export function LandingTechSpecsBar() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-32px" }}
      transition={{ duration: 0.45, ease: [0.25, 0.1, 0.25, 1] }}
      className="border-y border-zinc-800/90 bg-surface-base"
    >
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-8 gap-y-3 px-4 py-6 sm:px-6">
        {specs.map((label, i) => (
          <span key={label} className="flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-zinc-400">
            {i > 0 && (
              <span className="hidden text-zinc-700 sm:inline" aria-hidden>
                |
              </span>
            )}
            <span className="text-zinc-300">{label}</span>
          </span>
        ))}
      </div>
    </motion.div>
  );
}
