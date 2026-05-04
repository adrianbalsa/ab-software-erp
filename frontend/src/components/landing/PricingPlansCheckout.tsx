"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Check, Loader2, Minus } from "lucide-react";
import { toast } from "sonner";

import type { Catalog } from "@/i18n/catalog";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { apiFetch } from "@/lib/api";
import {
  buildPublicPlanTiers,
  normalizePlanQueryParam,
  resolvePublicStripePriceIds,
  stripeCheckoutReady,
  type PublicPlanSlug,
  type PublicPlanTier,
} from "@/lib/productPlans";

type Variant = "marketing-section" | "full-page";

function tierMarketingName(tier: PublicPlanTier, locale: string): string {
  return locale === "en" ? tier.marketingNameEn : tier.marketingNameEs;
}

function tierTagline(c: Catalog, slug: PublicPlanSlug): string {
  const p = c.pricing;
  if (slug === "starter") return p.starterDesc;
  if (slug === "pro") return p.proDesc;
  return p.entDesc;
}

function tierLimitsCaption(tier: PublicPlanTier, locale: string): string {
  return locale === "en" ? tier.limitsLineEn : tier.limitsLineEs;
}

function tierPriceLabel(tier: PublicPlanTier): string {
  const suffix = tier.priceSuffix ?? "";
  return `${tier.priceEur}€${suffix}`;
}

function defaultSalesHref(): string {
  const raw = (process.env.NEXT_PUBLIC_SALES_CONTACT ?? "").trim();
  if (raw) return raw;
  return "mailto:ventas@ablogistics.es?subject=Suscripci%C3%B3n%20AB%20Logistics%20OS";
}

export function PricingPlansCheckout({ variant }: { variant: Variant }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const empresaId = (searchParams.get("empresa_id") ?? "").trim();
  const planParam = searchParams.get("plan");
  const { catalog, locale } = useOptionalLocaleCatalog();
  const l = catalog.landing.pricing;
  const lp = catalog.landing.pricingPage;
  const [loadingTier, setLoadingTier] = useState<string | null>(null);
  const cardRefs = useRef<Partial<Record<PublicPlanSlug, HTMLDivElement | null>>>({});

  const ids = useMemo(() => resolvePublicStripePriceIds(), []);
  const checkoutOk = useMemo(() => stripeCheckoutReady(ids), [ids]);
  const tiers = useMemo(() => buildPublicPlanTiers(ids), [ids]);

  const highlightedSlug = useMemo(() => normalizePlanQueryParam(planParam), [planParam]);

  useEffect(() => {
    const el = cardRefs.current[highlightedSlug];
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightedSlug]);

  const loginThenPricingHref = (slug: PublicPlanSlug) =>
    `/login?next=${encodeURIComponent(`/pricing?plan=${encodeURIComponent(slug)}`)}`;

  const handlePrimaryCta = async (tier: PublicPlanTier) => {
    const priceId = tier.stripePriceId;
    if (!checkoutOk) {
      window.location.href = defaultSalesHref();
      return;
    }
    if (!priceId.trim()) {
      toast.error(l.missingStripeConfig);
      return;
    }
    if (!empresaId) {
      router.push(loginThenPricingHref(tier.slug));
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

  const TitleTag = variant === "full-page" ? "h1" : "h2";

  return (
    <div
      className={
        variant === "full-page"
          ? "mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-16"
          : "mx-auto max-w-6xl"
      }
    >
      <div className={variant === "marketing-section" ? "text-center mb-12" : "text-center mb-10 sm:mb-12"}>
        <TitleTag
          className={
            variant === "full-page"
              ? "text-3xl font-bold tracking-tight text-white sm:text-4xl"
              : "text-2xl font-bold tracking-tight text-white sm:text-3xl"
          }
        >
          {variant === "full-page" ? lp.title : l.title}
        </TitleTag>
        <p className="mt-3 text-pretty text-sm text-zinc-300 sm:text-base max-w-3xl mx-auto">
          {variant === "full-page" ? lp.subtitle : l.subtitle}
        </p>
        {variant === "full-page" && !empresaId ? (
          <p className="mt-4 text-pretty text-sm text-amber-200/90 max-w-2xl mx-auto">{lp.empresaRequiredHint}</p>
        ) : null}
        {variant === "full-page" && checkoutOk ? (
          <p className="mt-3 text-xs text-zinc-500 max-w-2xl mx-auto">{lp.stripeEnvHint}</p>
        ) : null}
      </div>

      {!checkoutOk ? (
        <div
          role="status"
          className="mb-8 rounded-2xl border border-amber-500/20 bg-amber-950/25 px-4 py-4 text-left sm:px-6 sm:py-5 max-w-6xl mx-auto"
        >
          <p className="text-sm font-semibold text-amber-50">{l.pricingStripeFallbackTitle}</p>
          <p className="mt-2 text-sm leading-relaxed text-amber-100/90">{l.pricingStripeFallbackBody}</p>
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <Link
              href="/help/billing"
              className="font-medium text-emerald-400/95 underline-offset-2 hover:text-emerald-300 hover:underline"
            >
              {l.pricingHelpBillingLink}
            </Link>
            {variant === "full-page" ? (
              <span className="text-xs text-amber-100/70">{lp.envVarsList}</span>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {tiers.map((tier) => {
          const ring = highlightedSlug === tier.slug;
          const name = tierMarketingName(tier, locale);
          return (
            <div
              key={tier.slug}
              ref={(node) => {
                cardRefs.current[tier.slug] = node;
              }}
              className={`relative flex flex-col rounded-3xl border p-8 transition-shadow duration-300 ${
                tier.highlight
                  ? "border-emerald-400/60 bg-gradient-to-b from-emerald-500/10 to-zinc-900/90 shadow-2xl shadow-emerald-500/10 ring-2 ring-emerald-500/30 md:-translate-y-1 md:scale-[1.02]"
                  : "border-zinc-800 bg-zinc-900/60"
              } ${ring ? "ring-2 ring-sky-400/50 shadow-[0_0_0_1px_rgba(56,189,248,0.2)]" : ""}`}
            >
              {tier.highlight && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-emerald-500 px-3 py-0.5 text-xs font-bold uppercase tracking-wide text-zinc-950">
                  {l.recommended}
                </span>
              )}
              <h3 className="text-lg font-bold tracking-tight text-white">{name}</h3>
              <p className="mt-2 text-sm leading-relaxed text-zinc-400">{tierTagline(catalog, tier.slug)}</p>
              <div className="mt-6 flex items-baseline gap-1">
                <span className="text-4xl font-extrabold text-white">{tierPriceLabel(tier)}</span>
                <span className="text-zinc-400">{l.monthSuffix}</span>
              </div>
              <p className="mt-1 text-xs text-zinc-500">{l.vatExcluded}</p>
              <p className="mt-2 text-xs font-medium text-zinc-400">{tierLimitsCaption(tier, locale)}</p>
              <ul className="mt-6 flex-1 divide-y divide-zinc-800/80 rounded-2xl border border-zinc-800/80 bg-surface-elevated text-sm">
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
                onClick={() => void handlePrimaryCta(tier)}
                disabled={(checkoutOk && !tier.stripePriceId.trim()) || loadingTier === tier.stripePriceId}
                title={checkoutOk && !tier.stripePriceId ? l.missingStripeConfig : undefined}
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
                  ) : checkoutOk && empresaId ? (
                    l.subscribeCta
                  ) : checkoutOk && !empresaId ? (
                    l.ctaLoginToSubscribe
                  ) : (
                    l.contactSalesCta
                  )}
                </span>
              </button>
            </div>
          );
        })}
      </div>

      {variant === "full-page" ? (
        <div className="mt-12 flex flex-col items-center gap-4 text-center">
          <p className="text-sm text-zinc-400 max-w-xl">{lp.funnelHint}</p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/login?next=%2Fpricing"
              className="inline-flex min-h-11 items-center justify-center rounded-full border border-zinc-600 bg-zinc-900/60 px-6 py-2.5 text-sm font-semibold text-zinc-100 transition hover:bg-zinc-800"
            >
              {lp.loginCta}
            </Link>
            <Link href="/" className="text-sm font-medium text-emerald-400 hover:text-emerald-300">
              {lp.backHome}
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}
