"use client";

import { motion } from "framer-motion";
import { FileCheck2, Lock, Scale, Shield } from "lucide-react";
import Link from "next/link";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.25, 0.1, 0.25, 1] as const } },
};

const items = [
  {
    icon: Shield,
    title: "Cumplimiento VeriFactu 2026",
    body: "Factura verificable, trazabilidad AEAT e integridad de registros según Ley 11/2021 y normativa de desarrollo vigente.",
    href: "/legal/verifactu",
    cta: "Ver anexo técnico",
  },
  {
    icon: Lock,
    title: "Datos y PSD2",
    body: "Tratamiento RGPD; agregación bancaria vía proveedores regulados — sin almacenar credenciales de banca electrónica en nuestra plataforma.",
    href: "/legal/privacidad",
    cta: "Política de privacidad",
  },
  {
    icon: Scale,
    title: "Marco legal completo",
    body: "Términos, cookies, aviso LSSI y limitaciones de responsabilidad transparentes para compras B2B y flotas enterprise.",
    href: "/legal",
    cta: "Marco legal",
  },
];

export function SecurityTrustSection() {
  return (
    <section id="seguridad" className="scroll-mt-24 bg-zinc-950 py-20 text-zinc-300">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <motion.div
          variants={fadeUp}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          className="mx-auto max-w-3xl text-center"
        >
          <div className="mx-auto mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-widest text-emerald-400/95">
            <FileCheck2 className="h-3.5 w-3.5" aria-hidden />
            Seguridad & confianza enterprise
          </div>
          <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
            Diseñado para auditorías, no solo para demos
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-zinc-400 sm:text-base">
            Transparencia legal y garantías de cumplimiento fiscal desde el primer contacto — el mismo estándar que
            esperarías de un ERP de categoría superior.
          </p>
        </motion.div>

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {items.map((item, i) => {
            const Icon = item.icon;
            return (
              <motion.div
                key={item.title}
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                transition={{ delay: i * 0.06 }}
                className="flex flex-col rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 shadow-xl shadow-black/20 backdrop-blur-sm"
              >
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-zinc-700 to-emerald-700 text-white shadow-lg">
                  <Icon className="h-5 w-5" aria-hidden />
                </div>
                <h3 className="text-lg font-bold text-white">{item.title}</h3>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-zinc-400">{item.body}</p>
                <Link
                  href={item.href}
                  className="mt-5 inline-flex text-sm font-semibold text-emerald-400 transition-colors hover:text-emerald-300"
                >
                  {item.cta} →
                </Link>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
