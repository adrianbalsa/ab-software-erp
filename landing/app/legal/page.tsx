import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Marco legal | AB Logistics OS",
  description:
    "Términos y condiciones, privacidad (RGPD), cumplimiento VeriFactu y política de cookies de AB Logistics OS.",
};

const DOCS = [
  {
    href: "/legal/terminos",
    title: "Términos y Condiciones",
    desc: "Condiciones de uso del SaaS, transporte de mercancías, mapas y disponibilidad del servicio (SLA).",
  },
  {
    href: "/legal/privacidad",
    title: "Política de Privacidad (RGPD)",
    desc: "Tratamiento de datos personales, geolocalización, telemetría y servicios bancarios PSD2.",
  },
  {
    href: "/legal/verifactu",
    title: "Anexo de Cumplimiento VeriFactu",
    desc: "Declaración técnica sobre integridad, conservación e inalterabilidad de registros de facturación.",
  },
  {
    href: "/legal/cookies",
    title: "Política de Cookies",
    desc: "Cookies y tecnologías similares conforme a la normativa aplicable en España y la UE.",
  },
  {
    href: "/aviso-legal",
    title: "Aviso legal (LSSI)",
    desc: "Datos identificativos del titular y información general del sitio.",
  },
];

export default function LegalIndexPage() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-4 px-4 py-6">
          <Link
            href="/"
            className="text-sm font-medium text-indigo-600 transition-colors hover:text-indigo-700"
          >
            ← AB Logistics OS
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-10 pb-16">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Marco legal</h1>
        <p className="mt-3 text-sm leading-relaxed text-slate-600">
          Documentación contractual y de cumplimiento normativo de la plataforma AB Logistics OS. Estos textos están
          redactados con criterios de transparencia orientados a clientes enterprise; no sustituyen el asesoramiento
          jurídico particular que pueda requerir su organización.
        </p>
        <ul className="mt-10 space-y-4">
          {DOCS.map((d) => (
            <li key={d.href}>
              <Link
                href={d.href}
                className="block rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
              >
                <span className="font-semibold text-slate-900">{d.title}</span>
                <p className="mt-2 text-sm text-slate-600">{d.desc}</p>
              </Link>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
