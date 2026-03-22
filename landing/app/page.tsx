"use client";
import { useState, useEffect } from "react";
import { motion, AnimatePresence, Variants } from "framer-motion";
import {
  Shield,
  Smartphone,
  BarChart3,
  Calculator,
  Clock,
  FileText,
  Check,
  Menu,
  X,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  ChevronRight,
} from "lucide-react";

import { EnterpriseShowcase } from "@/components/EnterpriseShowcase";
import { SecurityTrustSection } from "@/components/SecurityTrustSection";
import { LOGIN_URL, START_NOW_URL } from "@/components/site";

// ─── CONSTANTS ───────────────────────────────────────────────────────────────
const NAV_LINKS = [
  { label: "Producto", href: "#producto" },
  { label: "Funcionalidades", href: "#funcionalidades" },
  { label: "Precios", href: "#precios" },
  { label: "Calculadora ROI", href: "#calculadora" },
  { label: "Seguridad", href: "#seguridad" },
];

const FEATURES = [
  {
    icon: Shield,
    title: "Certificación VeriFactu",
    description: "Facturación blindada y conectada con la AEAT. Evita sanciones cumpliendo la Ley Antifraude 2026 de forma automática.",
    color: "text-indigo-600",
    bg: "bg-indigo-50",
  },
  {
    icon: BarChart3,
    title: "EBITDA en Tiempo Real",
    description: "Cruza ingresos con gastos de combustible, peajes y amortización para saber exactamente qué rutas son rentables.",
    color: "text-emerald-600",
    bg: "bg-emerald-50",
  },
  {
    icon: Smartphone,
    title: "Portal del Chófer",
    description: "Tus conductores suben tickets y CMRs con una foto desde el móvil. Cero papeleo perdido en la cabina del camión.",
    color: "text-blue-600",
    bg: "bg-blue-50",
  },
  {
    icon: Calculator,
    title: "Cotizador Inteligente",
    description: "Calcula el precio mínimo al que debes aceptar un viaje para no perder dinero, considerando los costes variables actuales.",
    color: "text-amber-600",
    bg: "bg-amber-50",
  },
  {
    icon: Clock,
    title: "Control de Vencimientos",
    description: "Alertas automáticas para renovaciones de ITV, seguros, tarjetas de transporte y mantenimientos preventivos.",
    color: "text-rose-600",
    bg: "bg-rose-50",
  },
  {
    icon: FileText,
    title: "Liquidaciones Automáticas",
    description: "Genera el pago de dietas y nóminas variables de tus conductores en un clic en base a los viajes registrados.",
    color: "text-cyan-600",
    bg: "bg-cyan-50",
  },
];

const PLANS = [
  {
    name: "Starter",
    price: "19",
    description: "Cumplimiento legal y control básico para autónomos.",
    popular: false,
    features: [
      "Hasta 2 vehículos",
      "Facturación VeriFactu obligatoria",
      "Portal móvil para 2 chóferes",
      "Gestión de gastos básicos",
      "Soporte por email (48h)",
    ],
  },
  {
    name: "Pro",
    price: "49",
    description: "Control de rentabilidad para flotas en crecimiento.",
    popular: true,
    features: [
      "Hasta 15 vehículos",
      "Dashboard de EBITDA en tiempo real",
      "Simulador de rentabilidad por porte",
      "Control de vencimientos (ITV, Seguros)",
      "Soporte prioritario (24h)",
    ],
  },
  {
    name: "Enterprise",
    price: "89",
    description: "Analítica avanzada y automatización total.",
    popular: false,
    features: [
      "Vehículos ilimitados",
      "Liquidación automática de chóferes",
      "Integración API con bancos",
      "Gestión multi-empresa",
      "Gestor de cuenta personal",
    ],
  },
];

// ─── FADE-UP ANIMATION VARIANT ────────────────────────────────────────────────
const fadeUp: Variants = {
  hidden: { opacity: 0, y: 28 },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, delay: i * 0.1, ease: [0.25, 0.1, 0.25, 1] },
  }),
};

// ─── NAVBAR ───────────────────────────────────────────────────────────────────
function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <motion.nav
      initial={{ y: -60, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? "border-b border-zinc-200/80 bg-[#f4f6fb]/95 shadow-sm backdrop-blur-sm"
          : "bg-transparent"
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <a href="/" className="flex items-center gap-2 group">
            <img src="/logo.png" alt="AB Logo" className="w-9 h-9 object-contain" />
            <span className="font-bold text-zinc-900 text-[15px] tracking-tight">
              AB Logistics OS
            </span>
          </a>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-8">
            {NAV_LINKS.map((l) => (
              <a
                key={l.label}
                href={l.href}
                className="text-sm font-medium text-zinc-600 transition-colors hover:text-emerald-800"
              >
                {l.label}
              </a>
            ))}
          </div>

          {/* Desktop CTAs */}
          <div className="hidden md:flex items-center gap-3">
            <a
              href="mailto:hola@ablogistics-os.com"
              className="ab-cta-outline rounded-xl px-4 py-2.5 text-sm"
            >
              Contactar
            </a>
            <a href={START_NOW_URL} className="ab-cta rounded-xl px-5 py-2.5 text-sm">
              Empezar ahora
            </a>
          </div>

          {/* Mobile hamburger */}
          <button
            className="md:hidden p-2 rounded-lg text-slate-700"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden overflow-hidden border-b border-zinc-100 bg-[#f4f6fb] px-4 pb-4"
          >
            <div className="flex flex-col gap-3 pt-2">
              {NAV_LINKS.map((l) => (
                <a
                  key={l.label}
                  href={l.href}
                  onClick={() => setMobileOpen(false)}
                  className="text-sm font-medium text-slate-700 py-2 border-b border-slate-50"
                >
                  {l.label}
                </a>
              ))}
              <a href={START_NOW_URL} className="ab-cta mt-2 rounded-xl px-4 py-2.5 text-center text-sm">
                Empezar ahora
              </a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  );
}

// ─── HERO ─────────────────────────────────────────────────────────────────────
function Hero() {
  return (
    <section className="relative flex min-h-screen items-center overflow-hidden bg-gradient-to-b from-[#f4f6fb] via-white to-emerald-50/40 pt-16">
      {/* Subtle grid background */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(#27272a 1px, transparent 1px), linear-gradient(90deg, #27272a 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />
      <div className="pointer-events-none absolute -right-40 top-0 h-[520px] w-[520px] rounded-full bg-emerald-400/20 blur-3xl" />
      <div className="pointer-events-none absolute -left-20 top-1/3 h-[380px] w-[380px] rounded-full bg-zinc-400/15 blur-3xl" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 text-center">
        {/* Badge */}
        <motion.div
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          custom={0}
          className="mb-8 inline-flex items-center gap-2 rounded-full border border-emerald-200/80 bg-emerald-50/90 px-4 py-1.5 text-xs font-semibold text-emerald-900"
        >
          <Shield className="w-3.5 h-3.5" />
          Adaptado a la normativa española VeriFactu 2026
        </motion.div>

        {/* Headline */}
        <motion.h1
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          custom={1}
          className="text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl"
        >
          <span className="bg-gradient-to-r from-zinc-900 via-zinc-800 to-zinc-900 bg-clip-text text-transparent">
            Inteligencia Logística y{" "}
          </span>
          <span className="bg-gradient-to-r from-emerald-700 to-emerald-600 bg-clip-text text-transparent">
            Control de Márgenes.
          </span>
        </motion.h1>

        {/* Subheadline */}
        <motion.p
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          custom={2}
          className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-zinc-600 sm:text-xl"
        >
          El ERP diseñado para proteger la rentabilidad de tu flota, automatizar
          la facturación y cumplir con la nueva Ley Antifraude (VeriFactu).
        </motion.p>

        {/* CTAs */}
        <motion.div
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          custom={3}
          className="mt-10 flex flex-col items-center gap-3"
        >
          <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
            <a href={START_NOW_URL} className="ab-cta inline-flex items-center gap-2 px-7 py-3.5 text-sm">
              Empezar ahora
              <ChevronRight className="h-4 w-4" aria-hidden />
            </a>
            <a
              href="mailto:hola@ablogistics-os.com"
              className="ab-cta-outline inline-flex items-center gap-2 px-7 py-3.5 text-sm shadow-sm"
            >
              Solicitar demo
            </a>
          </div>
          <a
            href={LOGIN_URL}
            className="text-xs font-medium text-zinc-500 underline-offset-4 hover:text-zinc-800 hover:underline"
          >
            Acceso con usuario y contraseña →
          </a>
        </motion.div>

        {/* Trust indicators */}
        <motion.div
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          custom={4}
          className="mt-6 flex flex-wrap items-center justify-center gap-6 text-xs text-zinc-500"
        >
          {["Soporte en España", "Onboarding en 24h", "VeriFactu 2026 incluido"].map((t) => (
            <span key={t} className="flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-emerald-600" aria-hidden />
              {t}
            </span>
          ))}
        </motion.div>

      </div>
    </section>
  );
}
// ─── ROI CALCULATOR ───────────────────────────────────────────────────────────
function ROICalculator() {
  const [income, setIncome] = useState(850);
  const [km, setKm] = useState(600);
  const [diesel, setDiesel] = useState(1.42);
  const [consumption, setConsumption] = useState(32);
  const [extras, setExtras] = useState(65);
  const [amort, setAmort] = useState(0.15);

  const fuelCost = (km / 100) * consumption * diesel;
  const amortCost = km * amort;
  const totalCost = fuelCost + amortCost + extras;
  const netProfit = income - totalCost;
  const margin = income > 0 ? (netProfit / income) * 100 : 0;
  const isLoss = netProfit < 0;

  const fmt = (n: number, dec = 2) =>
    n.toLocaleString("es-ES", { minimumFractionDigits: dec, maximumFractionDigits: dec });

  const InputField = ({
    label,
    value,
    onChange,
    suffix,
    step = 1,
  }: {
    label: string;
    value: number;
    onChange: (v: number) => void;
    suffix: string;
    step?: number;
  }) => (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">
        {label}
      </label>
      <div className="relative">
        <input
          type="number"
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          className="w-full bg-[#F8FAFC] border border-slate-200 rounded-xl px-4 py-2.5 text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-400 transition-all pr-10"
        />
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 font-medium">
          {suffix}
        </span>
      </div>
    </div>
  );

  return (
    <section id="calculadora" className="py-24 bg-[#F8FAFC]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          variants={fadeUp}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          className="text-center mb-12"
        >
          <span className="text-xs font-semibold uppercase tracking-widest text-emerald-800">
            Herramienta gratuita
          </span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-extrabold text-slate-900">
            Simulador de Rentabilidad por Porte
          </h2>
          <p className="mt-3 text-slate-500 max-w-xl mx-auto">
            Introduce los datos de tu viaje y descubre al instante si realmente
            estás ganando dinero.
          </p>
        </motion.div>

        <motion.div
          variants={fadeUp}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          custom={1}
          className="bg-[#F8FAFC] rounded-3xl shadow-sm border border-slate-100 overflow-hidden"
        >
          <div className="grid lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-slate-100">
            {/* Inputs */}
            <div className="p-8 lg:p-10">
              <h3 className="text-base font-semibold text-slate-900 mb-6">
                Datos del Porte
              </h3>
              <div className="grid sm:grid-cols-2 gap-5">
                <InputField
                  label="Ingreso del Viaje"
                  value={income}
                  onChange={setIncome}
                  suffix="€"
                />
                <InputField
                  label="Kilómetros Totales"
                  value={km}
                  onChange={setKm}
                  suffix="km"
                />
                <InputField
                  label="Precio Diésel"
                  value={diesel}
                  onChange={setDiesel}
                  suffix="€/L"
                  step={0.01}
                />
                <InputField
                  label="Consumo"
                  value={consumption}
                  onChange={setConsumption}
                  suffix="L/100km"
                  step={0.1}
                />
                <InputField
                  label="Peajes / Dietas"
                  value={extras}
                  onChange={setExtras}
                  suffix="€"
                />
                <InputField
                  label="Amortización/Km"
                  value={amort}
                  onChange={setAmort}
                  suffix="€/km"
                  step={0.01}
                />
              </div>
            </div>

            {/* Results */}
            <div className="p-8 lg:p-10 flex flex-col justify-center">
              <h3 className="text-base font-semibold text-slate-900 mb-6">
                Resultado en Tiempo Real
              </h3>

              {/* Cost breakdown */}
              <div className="space-y-3 mb-6">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Coste combustible</span>
                  <span className="font-semibold text-slate-700">
                    {fmt(fuelCost)} €
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Coste amortización</span>
                  <span className="font-semibold text-slate-700">
                    {fmt(amortCost)} €
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Peajes / Dietas</span>
                  <span className="font-semibold text-slate-700">
                    {fmt(extras)} €
                  </span>
                </div>
                <div className="flex justify-between text-sm border-t border-slate-100 pt-3">
                  <span className="text-slate-600 font-medium">Coste Total</span>
                  <span className="font-bold text-slate-900">{fmt(totalCost)} €</span>
                </div>
              </div>

              {/* Key metrics */}
              <div className="grid grid-cols-2 gap-4">
                <motion.div
                  key={netProfit}
                  initial={{ scale: 0.95 }}
                  animate={{ scale: 1 }}
                  transition={{ duration: 0.2 }}
                  className={`rounded-3xl p-6 border-2 transition-colors ${
                    isLoss
                      ? "bg-red-50 border-red-200"
                      : "bg-emerald-50 border-emerald-200"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-3">
                    {isLoss ? (
                      <TrendingDown className="w-5 h-5 text-red-500" />
                    ) : (
                      <TrendingUp className="w-5 h-5 text-emerald-600" />
                    )}
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                      Beneficio Neto
                    </span>
                  </div>
                  <p
                    className={`text-3xl sm:text-4xl font-black ${
                      isLoss ? "text-red-600" : "text-emerald-600"
                    }`}
                  >
                    {fmt(netProfit)} €
                  </p>
                </motion.div>

                <motion.div
                  key={margin}
                  initial={{ scale: 0.95 }}
                  animate={{ scale: 1 }}
                  transition={{ duration: 0.2 }}
                  className={`rounded-3xl p-6 border-2 transition-colors ${
                    isLoss
                      ? "bg-red-50 border-red-200"
                      : "bg-indigo-50 border-indigo-200"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <BarChart3
                      className={`w-5 h-5 ${
                        isLoss ? "text-red-500" : "text-indigo-600"
                      }`}
                    />
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                      Margen
                    </span>
                  </div>
                  <p
                    className={`text-3xl sm:text-4xl font-black ${
                      isLoss ? "text-red-600" : "text-indigo-700"
                    }`}
                  >
                    {fmt(margin, 1)}%
                  </p>
                </motion.div>
              </div>

              {/* Alert */}
              <AnimatePresence>
                {isLoss && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 8 }}
                    transition={{ duration: 0.3 }}
                    className="mt-4 flex items-start gap-3 bg-red-50 border border-red-200 rounded-2xl p-4"
                  >
                    <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-semibold text-red-700">
                        Viaje a pérdidas
                      </p>
                      <p className="text-xs text-red-500 mt-0.5">
                        No cubre amortización. Revisa el precio pactado o los
                        costes del viaje.
                      </p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ─── FEATURES ─────────────────────────────────────────────────────────────────
function Features() {
  return (
    <section id="funcionalidades" className="py-24 bg-[#F8FAFC]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          variants={fadeUp}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <span className="text-xs font-semibold uppercase tracking-widest text-emerald-800">
            Funcionalidades
          </span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-extrabold text-slate-900">
            Todo lo que necesita tu flota
          </h2>
          <p className="mt-3 text-slate-500 max-w-xl mx-auto">
            Diseñado específicamente para operadores de transporte español,
            desde autónomos hasta flotas medianas.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-6">
          {FEATURES.map((f, i) => {
            const Icon = f.icon;
            return (
              <motion.div
                key={f.title}
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                custom={i}
                whileHover={{ y: -6, boxShadow: "0 12px 32px rgba(30,58,138,0.10)" }}
                className="bg-[#F8FAFC] rounded-2xl border border-slate-100 p-8 cursor-default transition-shadow duration-200 shadow-sm"
              >
                <div className={`w-12 h-12 rounded-xl ${f.bg} flex items-center justify-center mb-6`}>
                  <Icon className={`w-6 h-6 ${f.color}`} />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-3">
                  {f.title}
                </h3>
                <p className="text-slate-500 text-sm leading-relaxed">
                  {f.description}
                </p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ─── PRICING ──────────────────────────────────────────────────────────────────
function Pricing() {
  return (
    <section id="precios" className="py-24 bg-[#F8FAFC]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          variants={fadeUp}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <span className="text-xs font-semibold uppercase tracking-widest text-emerald-800">
            Precios
          </span>
          <h2 className="mt-3 text-3xl sm:text-4xl font-extrabold text-slate-900">
            Planes simples y transparentes
          </h2>
          <p className="mt-3 text-slate-500 max-w-xl mx-auto">
            Sin costes ocultos. Escala cuando crezcas. Cancela cuando quieras.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-8 items-stretch max-w-6xl mx-auto">
          {PLANS.map((plan, i) => (
            <motion.div
              key={plan.name}
              variants={fadeUp}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true }}
              custom={i}
              className={`relative rounded-3xl p-8 flex flex-col border transition-all duration-300 ${
                plan.popular
                  ? "z-10 border-emerald-500 bg-slate-900 shadow-2xl shadow-emerald-950/30 md:-translate-y-4"
                  : "bg-white border-slate-200 shadow-sm hover:shadow-md"
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="rounded-full bg-gradient-to-r from-zinc-600 to-emerald-600 px-5 py-2 text-xs font-bold uppercase tracking-wider text-white shadow-md">
                    Más popular
                  </span>
                </div>
              )}

              <div className="mb-6">
                <h3
                  className={`text-xl font-bold mb-1 ${
                    plan.popular ? "text-[#F8FAFC]" : "text-slate-900"
                  }`}
                >
                  {plan.name}
                </h3>
                <p
                  className={`text-sm ${
                    plan.popular ? "text-blue-200" : "text-slate-500"
                  }`}
                >
                  {plan.description}
                </p>
              </div>

              <div className="mb-8">
                {plan.price === "Custom" ? (
                  <span
                    className={`text-3xl font-extrabold ${
                      plan.popular ? "text-[#F8FAFC]" : "text-slate-900"
                    }`}
                  >
                    A medida
                  </span>
                ) : (
                  <div className="flex items-end gap-1">
                    <span
                      className={`text-4xl font-extrabold ${
                        plan.popular ? "text-[#F8FAFC]" : "text-slate-900"
                      }`}
                    >
                      {plan.price}€
                    </span>
                    <span
                      className={`text-sm pb-1 ${
                        plan.popular ? "text-blue-200" : "text-slate-500"
                      }`}
                    >
                      /mes
                    </span>
                  </div>
                )}
              </div>

              <ul className="space-y-3 mb-8 flex-1">
                {plan.features.map((feat) => (
                  <li key={feat} className="flex items-center gap-3">
                    <div
                      className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                        plan.popular ? "bg-blue-600" : "bg-blue-50"
                      }`}
                    >
                      <Check
                        className={`w-3 h-3 ${
                          plan.popular ? "text-[#F8FAFC]" : "text-emerald-700"
                        }`}
                      />
                    </div>
                    <span
                      className={`text-sm ${
                        plan.popular ? "text-blue-100" : "text-slate-600"
                      }`}
                    >
                      {feat}
                    </span>
                  </li>
                ))}
              </ul>

              <a
                href={START_NOW_URL}
                className={`rounded-xl py-3 text-center text-sm font-semibold transition-all duration-200 ${
                  plan.popular
                    ? "border border-emerald-400/40 bg-white text-zinc-900 shadow-lg hover:bg-emerald-50"
                    : "ab-cta text-white shadow-lg"
                }`}
              >
                Empezar ahora
              </a>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── FOOTER ───────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer className="bg-zinc-950 py-16 text-zinc-400">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mb-10 rounded-2xl border border-zinc-800/80 bg-zinc-900/50 px-5 py-4 sm:flex sm:items-center sm:justify-between sm:gap-6">
          <p className="text-sm leading-relaxed text-zinc-300">
            <span className="font-semibold text-white">Cumplimiento VeriFactu 2026</span> · RGPD · Marco legal completo.
            Infraestructura orientada a flotas que auditan procesos.
          </p>
          <a
            href="/legal/verifactu"
            className="mt-3 inline-flex shrink-0 items-center text-sm font-semibold text-emerald-400 transition-colors hover:text-emerald-300 sm:mt-0"
          >
            Ver garantías legales →
          </a>
        </div>
        <div className="mb-12 grid gap-10 md:grid-cols-3">
          {/* Brand */}
          <div>
            <div className="mb-4 flex items-center gap-2">
              <img src="/logo.png" alt="AB Logo" className="h-8 w-8 object-contain" />
              <span className="text-sm font-bold text-zinc-100">AB Logistics OS</span>
            </div>
            <p className="text-sm leading-relaxed">
              Software de gestión de transporte y logística en Galicia.
              Desarrollado en A Coruña.
            </p>
          </div>

          {/* Links */}
          <div>
            <h4 className="mb-4 text-sm font-semibold text-zinc-100">Producto</h4>
            <ul className="space-y-2 text-sm">
              <li>
                <a href="#producto" className="transition-colors hover:text-zinc-100">
                  Vista del producto
                </a>
              </li>
              <li>
                <a href="#funcionalidades" className="transition-colors hover:text-zinc-100">
                  Funcionalidades
                </a>
              </li>
              <li>
                <a href="#precios" className="transition-colors hover:text-zinc-100">
                  Precios
                </a>
              </li>
              <li>
                <a href="#calculadora" className="transition-colors hover:text-zinc-100">
                  Calculadora ROI
                </a>
              </li>
              <li>
                <a href="#seguridad" className="transition-colors hover:text-zinc-100">
                  Seguridad y cumplimiento
                </a>
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="mb-4 text-sm font-semibold text-zinc-100">Legal</h4>
            <ul className="space-y-2 text-sm">
              <li>
                <a href="/legal" className="transition-colors hover:text-zinc-100">
                  Marco legal
                </a>
              </li>
              <li>
                <a href="/legal/terminos" className="transition-colors hover:text-zinc-100">
                  Términos y Condiciones
                </a>
              </li>
              <li>
                <a href="/legal/privacidad" className="transition-colors hover:text-zinc-100">
                  Política de Privacidad (RGPD)
                </a>
              </li>
              <li>
                <a href="/legal/verifactu" className="transition-colors hover:text-zinc-100">
                  Cumplimiento VeriFactu
                </a>
              </li>
              <li>
                <a href="/legal/cookies" className="transition-colors hover:text-zinc-100">
                  Política de Cookies
                </a>
              </li>
              <li>
                <a href="/aviso-legal" className="transition-colors hover:text-zinc-100">
                  Aviso legal (LSSI)
                </a>
              </li>
              <li>
                <a href="mailto:hola@ablogistics-os.com" className="transition-colors hover:text-zinc-100">
                  hola@ablogistics-os.com
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="flex flex-col items-center justify-between gap-4 border-t border-zinc-800 pt-8 text-xs sm:flex-row">
          <p>© 2026 AB Logistics OS. Todos los derechos reservados.</p>
          <p className="text-center text-zinc-500">
            Software de gestión de transporte y logística en Galicia · Desarrollado en A Coruña
          </p>
        </div>
      </div>
    </footer>
  );
}

// ─── PAGE ─────────────────────────────────────────────────────────────────────
export default function Page() {
  return (
    <main>
      <Navbar />
      <Hero />
      <EnterpriseShowcase />
      <ROICalculator />
      <Features />
      <SecurityTrustSection />
      <Pricing />
      <Footer />
    </main>
  );
}
