"use client";

import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { Brain, CreditCard, Leaf, Shield } from "lucide-react";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { cn } from "@/lib/utils";

type BentoItem = {
  title: string;
  body: string;
  icon: LucideIcon;
  span: "2" | "1";
  variant?: "fiscal" | "default";
};

const bentoIcons: Array<Pick<BentoItem, "icon" | "span" | "variant">> = [
  { icon: Shield, span: "2", variant: "fiscal" },
  { icon: Leaf, span: "1" },
  { icon: CreditCard, span: "1" },
  { icon: Brain, span: "2" },
];

/** Deterministic QR-like pattern (avoids SSR/client random mismatch). */
const QR_PATTERN = Array.from({ length: 64 }, (_, i) => ((i * 17 + (i % 9)) % 5 > 1 ? 1 : 0));

function QrHint() {
  return (
    <div
      className="pointer-events-none absolute -right-4 -top-4 grid grid-cols-8 gap-0.5 opacity-[0.14]"
      aria-hidden
    >
      {QR_PATTERN.map((on, i) => (
        <span
          key={i}
          className={cn("h-2 w-2 rounded-[1px]", on ? "bg-emerald-400" : "bg-transparent")}
        />
      ))}
    </div>
  );
}

function FiscalBackdrop() {
  return (
    <div
      className="pointer-events-none absolute inset-0 overflow-hidden rounded-2xl opacity-[0.07]"
      aria-hidden
    >
      <pre className="absolute -right-8 top-4 max-w-[min(100%,28rem)] whitespace-pre-wrap font-mono text-[10px] leading-relaxed text-emerald-200">
        {`<ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
  <ds:SignedInfo>
    <ds:CanonicalizationMethod Algorithm="..."/>
    <ds:SignatureMethod Algorithm="..."/>
  </ds:SignedInfo>
  <ds:SignatureValue>...</ds:SignatureValue>
</ds:Signature>`}
      </pre>
    </div>
  );
}

function BentoCard({
  item,
  index,
}: {
  item: BentoItem;
  index: number;
}) {
  const Icon = item.icon;
  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.5, delay: index * 0.06, ease: [0.25, 0.1, 0.25, 1] }}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6 transition-all duration-300",
        "hover:border-emerald-500/35 hover:shadow-[0_0_0_1px_rgba(16,185,129,0.12),0_0_48px_-16px_rgba(16,185,129,0.22)]",
        item.span === "2" ? "md:col-span-2" : "md:col-span-1",
      )}
    >
      {item.variant === "fiscal" && <FiscalBackdrop />}
      {item.variant === "fiscal" && <QrHint />}
      <div className="relative flex items-start gap-4">
        <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-950/80 text-emerald-500 transition group-hover:border-emerald-500/30 group-hover:text-emerald-400">
          <Icon className="h-5 w-5" strokeWidth={1.75} />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-semibold tracking-tight text-white">{item.title}</h2>
          <p className="mt-2 text-sm leading-relaxed text-zinc-400">{item.body}</p>
        </div>
      </div>
    </motion.article>
  );
}

export function LandingBentoGrid() {
  const { catalog } = useOptionalLocaleCatalog();
  const l = catalog.landing.bento;
  const items: BentoItem[] = l.cards.map((card, idx) => {
    const iconDef = bentoIcons[idx] ?? bentoIcons[0];
    return {
      ...card,
      ...iconDef,
    };
  });

  return (
    <section id="plataforma" className="scroll-mt-24 px-4 pb-20 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <p className="text-xs font-semibold uppercase tracking-widest text-zinc-500">{l.eyebrow}</p>
        <h2 className="mt-2 text-2xl font-semibold text-white sm:text-3xl">{l.title}</h2>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400 sm:text-base">{l.subtitle}</p>
        <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-3">
          {items.map((item, i) => (
            <BentoCard key={item.title} item={item} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
