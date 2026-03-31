"use client";

import { LandingFooter } from "./LandingFooter";
import { LandingHeader } from "./LandingHeader";
import { BarChart, Brain, Check, Leaf, Shield } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const pillarCards = [
  {
    title: "Fiscalidad Blindada",
    description:
      "Encadenamiento SHA-256 e inmutabilidad absoluta cumpliendo la Ley Antifraude y VeriFactu.",
    icon: Shield,
    className: "lg:col-span-2",
  },
  {
    title: "Tesorería Autónoma",
    description:
      "Conciliación IA de webhooks GoCardless con 95% de precisión. EBITDA real O(1) sin mover un dedo.",
    icon: Brain,
    className: "lg:col-span-1",
  },
  {
    title: "Pasaporte ESG",
    description:
      "Reportes certificados de CO2 (Alcance 1 y 3) bajo GLEC Framework. Cumpla hoy lo que sus cargadores exigirán mañana.",
    icon: Leaf,
    className: "lg:col-span-2",
  },
  {
    title: "Dirección Financiera",
    description:
      "KPIs ejecutivos en tiempo real para CFOs y propietarios de flota con trazabilidad auditable.",
    icon: BarChart,
    className: "lg:col-span-1",
  },
];

const pricingTiers = [
  {
    name: "Compliance",
    price: "79€/mes",
    subtitle: "Duerma tranquilo con Hacienda",
    features: ["VeriFactu", "Firma XAdES-BES", "QR Fingerprinting"],
    accent: false,
  },
  {
    name: "Business",
    price: "199€/mes",
    subtitle: "La Tesorería que piensa",
    features: [
      "Everything in Compliance",
      "Conciliación IA",
      "Dashboards BI O(1)",
      "Gestión de Cobros",
    ],
    accent: true,
  },
  {
    name: "Enterprise",
    price: "399€/mes",
    subtitle: "Licitaciones Corporativas Ganadas",
    features: [
      "Everything in Business",
      "Módulo ESG GLEC",
      "Matriz de Eficiencia",
      "Soporte Prioritario",
    ],
    accent: false,
  },
];

const faqs = [
  {
    q: "¿AB Logistics OS sustituye mi ERP actual?",
    a: "No. Se acopla como infraestructura crítica para fiscalidad, tesorería y ESG. Mantiene su ERP operativo y añade una capa de blindaje y control ejecutivo.",
  },
  {
    q: "¿Qué nivel de despliegue exige al equipo?",
    a: "Onboarding guiado con modelo plug-and-operate. Activación por fases sin interrumpir operaciones de transporte ni facturación diaria.",
  },
  {
    q: "¿Cómo se protege la trazabilidad ante auditoría?",
    a: "Cada hito financiero y fiscal queda registrado con inmutabilidad criptográfica y cadena verificable para inspecciones internas y regulatorias.",
  },
];

/** Landing original (tema oscuro) para el dominio de marketing. */
export function LandingPageDark() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <LandingHeader />
      <main>
        <section className="relative overflow-hidden px-4 pb-16 pt-20 sm:px-6 sm:pb-24 sm:pt-28">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(30,64,175,0.22),transparent_55%)]" />
          <div className="relative mx-auto max-w-6xl">
            <Badge className="border-blue-500/30 bg-blue-500/10 text-blue-200">
              AB Logistics OS
            </Badge>
            <h1 className="mt-6 max-w-4xl text-balance text-4xl font-semibold tracking-tight text-white sm:text-5xl lg:text-6xl">
              Su Logística es Real. Su Blindaje Fiscal debe ser Inmutable.
            </h1>
            <p className="mt-6 max-w-3xl text-pretty text-base text-zinc-300 sm:text-lg">
              El primer ecosistema autónomo para transporte que integra VeriFactu
              (AEAT), Conciliación Bancaria con IA y Sostenibilidad GLEC en una
              sola infraestructura de confianza.
            </p>
            <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-center">
              <Button
                asChild
                size="lg"
                className="h-12 rounded-full bg-emerald-500 px-8 text-sm font-semibold text-zinc-950 hover:bg-emerald-400"
              >
                <Link href="/login">
                  Solicitar Acceso al Búnker (8 Plazas Disponibles)
                </Link>
              </Button>
              <p className="text-xs uppercase tracking-[0.18em] text-zinc-400">
                Exclusivo para CFOs y propietarios de flota
              </p>
            </div>
          </div>
        </section>

        <section id="bunker-pillars" className="px-4 py-16 sm:px-6">
          <div className="mx-auto max-w-6xl">
            <h2 className="text-2xl font-semibold text-white sm:text-3xl">
              Los Pilares del Búnker
            </h2>
            <p className="mt-2 text-sm text-zinc-400 sm:text-base">
              Arquitectura diseñada para preservar caja, cumplimiento y ventaja
              competitiva.
            </p>
            <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
              {pillarCards.map((pillar) => {
                const Icon = pillar.icon;
                return (
                  <Card
                    key={pillar.title}
                    className={`border-zinc-800 bg-zinc-900/70 py-0 ${pillar.className}`}
                  >
                    <CardHeader className="px-6 pt-6">
                      <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl border border-zinc-700 bg-zinc-950">
                        <Icon className="h-5 w-5 text-emerald-300" />
                      </div>
                      <CardTitle className="text-lg font-semibold text-white">
                        {pillar.title}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="px-6 pb-6">
                      <CardDescription className="text-sm leading-relaxed text-zinc-300">
                        {pillar.description}
                      </CardDescription>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>
        </section>

        <section id="pricing" className="px-4 py-16 sm:px-6">
          <div className="mx-auto max-w-6xl">
            <h2 className="text-2xl font-semibold text-white sm:text-3xl">
              Estructura de Inversión
            </h2>
            <p className="mt-2 text-sm text-zinc-400 sm:text-base">
              Price Table para escalar desde cumplimiento a liderazgo corporativo.
            </p>
            <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
              {pricingTiers.map((tier) => (
                <Card
                  key={tier.name}
                  className={`border py-0 ${
                    tier.accent
                      ? "border-emerald-500/50 bg-gradient-to-b from-emerald-500/10 to-zinc-900/85 shadow-2xl shadow-emerald-900/30"
                      : "border-zinc-800 bg-zinc-900/65"
                  }`}
                >
                  <CardHeader className="px-6 pt-6">
                    <CardTitle className="text-xl font-semibold text-white">
                      {tier.name}
                    </CardTitle>
                    <CardDescription className="text-sm text-zinc-300">
                      {tier.subtitle}
                    </CardDescription>
                    <p className="pt-2 text-3xl font-semibold text-white">
                      {tier.price}
                    </p>
                  </CardHeader>
                  <CardContent className="px-6 pb-6">
                    <ul className="space-y-3">
                      {tier.features.map((feature) => (
                        <li
                          key={`${tier.name}-${feature}`}
                          className="flex items-center gap-2 text-sm text-zinc-200"
                        >
                          <Check className="h-4 w-4 text-emerald-300" />
                          {feature}
                        </li>
                      ))}
                    </ul>
                    <Button
                      asChild
                      className="mt-6 h-11 w-full rounded-full bg-zinc-100 text-zinc-900 hover:bg-white"
                      size="lg"
                    >
                      <Link href="/login">Solicitar Acceso al Búnker</Link>
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="px-4 py-16 sm:px-6">
          <div className="mx-auto max-w-6xl">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-8 sm:p-10">
              <p className="text-xl font-medium leading-relaxed text-white sm:text-2xl">
                No compre un ERP. Adquiera la infraestructura que su competencia
                tardará 20 meses y 300.000€ en replicar. El tiempo es su mayor
                foso defensivo.
              </p>
            </div>
          </div>
        </section>

        <section id="faq" className="px-4 pb-20 sm:px-6">
          <div className="mx-auto max-w-4xl">
            <h2 className="text-2xl font-semibold text-white sm:text-3xl">
              Decisiones de Dirección
            </h2>
            <div className="mt-6 space-y-3">
              {faqs.map((item) => (
                <details
                  key={item.q}
                  className="group rounded-xl border border-zinc-800 bg-zinc-900/60 p-5"
                >
                  <summary className="cursor-pointer list-none text-sm font-semibold text-zinc-100 sm:text-base">
                    {item.q}
                  </summary>
                  <p className="mt-3 text-sm leading-relaxed text-zinc-300">
                    {item.a}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>
      </main>
      <LandingFooter />
    </div>
  );
}

