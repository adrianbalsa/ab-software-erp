"use client";

import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Check, Minus, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { FadeInSection } from "./FadeInSection";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { apiFetch } from "@/lib/api";

function stripePriceIds() {
  return {
    compliance: (
      process.env.NEXT_PUBLIC_STRIPE_PRICE_BASIC ??
      process.env.NEXT_PUBLIC_STRIPE_PRICE_STARTER ??
      ""
    ).trim(),
    finance: (process.env.NEXT_PUBLIC_STRIPE_PRICE_PRO ?? "").trim(),
    enterprise: (process.env.NEXT_PUBLIC_STRIPE_PRICE_ENTERPRISE ?? "").trim(),
  };
}

export function LandingPricing() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const empresaId = (searchParams.get("empresa_id") ?? "").trim();
  const [loadingTier, setLoadingTier] = useState<string | null>(null);
  const { catalog } = useOptionalLocaleCatalog();
  const l = catalog.landing.pricing;

  const { tiers, stripeCheckoutReady } = useMemo(() => {
    const ids = stripePriceIds();
    const stripeCheckoutReady = Boolean(ids.compliance && ids.finance && ids.enterprise);
    const tiersLocal = [
      {
        name: "Compliance",
        price: "39",
        stripePriceId: ids.compliance,
        includes: [true, true, false, false, false, false] as const,
        highlight: false,
      },
      {
        name: "Finance",
        price: "149",
        stripePriceId: ids.finance,
        includes: [true, true, true, true, true, false] as const,
        highlight: true,
      },
      {
        name: "Enterprise",
        price: "399",
        stripePriceId: ids.enterprise,
        includes: [true, true, true, true, true, true] as const,
        highlight: false,
      },
    ];
    return { tiers: tiersLocal, stripeCheckoutReady };
  }, []);

  const handleSuscripcion = async (priceId: string, planName: string) => {
    if (!priceId.trim()) {
      toast.error(l.missingStripeConfig);
      return;
    }
    if (!empresaId) {
      const plan = planName.toLowerCase();
      const target = `/pricing${plan ? `?plan=${encodeURIComponent(plan)}` : ""}`;
      router.push(target);
      return;
    }
    setLoadingTier(priceId);
    try {
      const response = await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/stripe/crear-sesion-checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ price_id: priceId, empresa_id: empresaId }),
      });

      const data = await response.json();

      if (data.url) {
        window.location.href = data.url;
      } else {
        toast.error(l.stripeGatewayError);
      }
    } catch {
      toast.error(l.stripeConnectionError);
    } finally {
      setLoadingTier(null);
    }
  };

  return (
    <FadeInSection
      id="pricing"
      className="scroll-mt-20 bg-surface-section px-4 py-24 sm:px-6 sm:py-28"
    >
      <div className="mx-auto max-w-6xl">
        <div className="text-center mb-12">
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">{l.title}</h2>
          <p className="mt-2 text-zinc-300 text-sm sm:text-base">{l.subtitle}</p>
        </div>

        {!stripeCheckoutReady ? (
          <div
            role="status"
            className="mb-8 rounded-2xl border border-amber-500/25 bg-amber-950/35 px-4 py-3 text-left sm:px-5 sm:py-4"
          >
            <p className="text-sm font-semibold text-amber-100">{l.pricingStripeFallbackTitle}</p>
            <p className="mt-1 text-sm leading-relaxed text-amber-100/85">{l.pricingStripeFallbackBody}</p>
          </div>
        ) : null}

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
                  {l.recommended}
                </span>
              )}
              <h3 className="text-lg font-bold tracking-tight text-white">{tier.name}</h3>
              <div className="mt-6 flex items-baseline gap-1">
                <span className="text-4xl font-extrabold text-white">{tier.price}€</span>
                <span className="text-zinc-400">{l.monthSuffix}</span>
              </div>
              <p className="mt-1 text-xs text-zinc-500">IVA no incluido</p>
              <ul className="mt-8 flex-1 divide-y divide-zinc-800/80 rounded-2xl border border-zinc-800/80 bg-surface-elevated text-sm">
                {l.features.map((feature, index) => (
                  <li key={feature} className="flex items-center justify-between gap-2 px-3 py-2.5 text-zinc-300">
                    <span>{feature}</span>
                    {tier.includes[index] ? (
                      <Check className="h-4 w-4 shrink-0 text-emerald-400" />
                    ) : (
                      <Minus className="h-4 w-4 shrink-0 text-zinc-500" />
                    )}
                  </li>
                ))}
              </ul>

              <button
                type="button"
                onClick={() => void handleSuscripcion(tier.stripePriceId, tier.name)}
                disabled={!tier.stripePriceId || loadingTier === tier.stripePriceId}
                title={!tier.stripePriceId ? l.missingStripeConfig : undefined}
                className={`mt-8 flex min-h-11 w-full items-center justify-center gap-2 rounded-full px-4 py-3 text-sm font-semibold transition ${
                  tier.highlight
                    ? "bg-emerald-500 text-zinc-950 hover:bg-emerald-400 disabled:bg-emerald-500/50"
                    : "border border-zinc-600 text-zinc-200 hover:bg-zinc-800 disabled:opacity-50"
                }`}
              >
                <span className="inline-flex min-w-[8rem] items-center justify-center gap-2">
                  {loadingTier === tier.stripePriceId ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      {l.connecting}
                    </>
                  ) : (
                    l.requestAccess
                  )}
                </span>
              </button>
            </div>
          ))}
        </div>
      </div>
    </FadeInSection>
  );
}
