"use client";

import { useState } from "react";
import { Check, Minus, Loader2 } from "lucide-react";
import { FadeInSection } from "./FadeInSection";
import { apiFetch } from "@/lib/api";

/** IDs de precio Stripe (`price_…`); configurar en `.env` del frontend para checkout público. */
const stripePriceCompliance = process.env.NEXT_PUBLIC_STRIPE_PRICE_STARTER ?? "";
const stripePriceFinance = process.env.NEXT_PUBLIC_STRIPE_PRICE_PRO ?? "";
const stripePriceFullStack = process.env.NEXT_PUBLIC_STRIPE_PRICE_ENTERPRISE ?? "";

const tiers = [
  {
    name: "Compliance",
    price: "39",
    stripePriceId: stripePriceCompliance,
    includes: [true, true, false, false, false, false],
    highlight: false,
  },
  {
    name: "Finance",
    price: "149",
    stripePriceId: stripePriceFinance,
    includes: [true, true, true, true, true, false],
    highlight: true,
  },
  {
    name: "Full-Stack",
    price: "449",
    stripePriceId: stripePriceFullStack,
    includes: [true, true, true, true, true, true],
    highlight: false,
  },
];

const comparedFeatures = [
  "Certificación VeriFactu",
  "EBITDA en Tiempo Real",
  "Portal del Chófer",
  "Cotizador Inteligente",
  "Control de Vencimientos",
  "Liquidaciones Automáticas",
];

export function LandingPricing() {
  const [loadingTier, setLoadingTier] = useState<string | null>(null);

  const handleSuscripcion = async (priceId: string) => {
    if (!priceId.trim()) {
      alert(
        "Falta configurar los Price IDs de Stripe en el frontend (NEXT_PUBLIC_STRIPE_PRICE_*). Consulta docs/operations/STRIPE_BILLING.md.",
      );
      return;
    }
    setLoadingTier(priceId);
    try {
      const response = await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/stripe/crear-sesion-checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ price_id: priceId, user_id: "USUARIO_PENDIENTE_DE_REGISTRO" }),
      });

      const data = await response.json();

      if (data.url) {
        window.location.href = data.url;
      } else {
        alert("Hubo un problema al conectar con la pasarela segura.");
      }
    } catch {
      alert("No se pudo conectar con la pasarela segura. Inténtalo de nuevo.");
    } finally {
      setLoadingTier(null);
    }
  };

  return (
    <FadeInSection id="pricing" className="scroll-mt-24 px-4 py-16 sm:px-6 bg-zinc-950/40">
      <div className="mx-auto max-w-6xl">
        <div className="text-center mb-12">
          <h2 className="text-2xl font-bold text-white sm:text-3xl">Precios claros</h2>
          <p className="mt-2 text-zinc-400 text-sm sm:text-base">
            Inversión mensual orientada a ROI operativo: cada euro debe volver en eficiencia y control de margen.
            Cifras orientativas + IVA; add-ons (OCR, webhooks premium, IA Pro) documentados en el repositorio
            bajo docs/operations/STRIPE_BILLING.md.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {tiers.map((tier) => (
            <div
              key={tier.name}
              className={`relative flex flex-col rounded-3xl border p-8 ${
                tier.highlight
                  ? "border-emerald-400/60 bg-gradient-to-b from-emerald-500/10 to-zinc-900/90 shadow-2xl shadow-emerald-500/10 ring-2 ring-emerald-500/30 md:-translate-y-1 md:scale-[1.02]"
                  : "border-zinc-800 bg-zinc-900/60"
              }`}
            >
              {tier.highlight && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-emerald-500 px-3 py-0.5 text-xs font-bold uppercase tracking-wide text-zinc-950">
                  Recomendado
                </span>
              )}
              <h3 className="text-lg font-bold text-white">{tier.name}</h3>
              <div className="mt-6 flex items-baseline gap-1">
                <span className="text-4xl font-extrabold text-white">{tier.price}€</span>
                <span className="text-zinc-500">/mes</span>
              </div>
              <ul className="mt-8 flex-1 divide-y divide-zinc-800/80 rounded-2xl border border-zinc-800/80 bg-zinc-950/40 text-sm">
                {comparedFeatures.map((feature, index) => (
                  <li key={feature} className="flex items-center justify-between gap-2 px-3 py-2.5 text-zinc-300">
                    <span>{feature}</span>
                    {tier.includes[index] ? (
                      <Check className="h-4 w-4 shrink-0 text-emerald-400" />
                    ) : (
                      <Minus className="h-4 w-4 shrink-0 text-zinc-600" />
                    )}
                  </li>
                ))}
              </ul>

              <button
                type="button"
                onClick={() => void handleSuscripcion(tier.stripePriceId)}
                disabled={loadingTier === tier.stripePriceId}
                className={`mt-8 flex w-full items-center justify-center gap-2 rounded-full py-3 text-sm font-semibold transition ${
                  tier.highlight
                    ? "bg-emerald-500 text-zinc-950 hover:bg-emerald-400 disabled:bg-emerald-500/50"
                    : "border border-zinc-600 text-zinc-200 hover:bg-zinc-800 disabled:opacity-50"
                }`}
              >
                {loadingTier === tier.stripePriceId ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Conectando...
                  </>
                ) : (
                  "Solicitar Acceso al Sistema"
                )}
              </button>
            </div>
          ))}
        </div>
      </div>
    </FadeInSection>
  );
}
