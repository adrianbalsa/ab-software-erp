/**
 * Catálogo público de planes SaaS — alineado con `backend/app/core/plans.py`
 * y Stripe (Price IDs vía NEXT_PUBLIC_STRIPE_PRICE_*).
 *
 * Slugs canónicos en BD: starter | pro | enterprise
 * Nombres comerciales UI: Essential | Pro | Enterprise
 */

export const PLAN_SLUG_STARTER = "starter" as const;
export const PLAN_SLUG_PRO = "pro" as const;
export const PLAN_SLUG_ENTERPRISE = "enterprise" as const;

export type PlanSlug = typeof PLAN_SLUG_STARTER | typeof PLAN_SLUG_PRO | typeof PLAN_SLUG_ENTERPRISE;

/** EUR/mes catálogo (referencia; cargo real = Price en Stripe). */
export const EUR_MONTHLY_ESSENTIAL = 350;
export const EUR_MONTHLY_PRO = 800;
export const EUR_MONTHLY_ENTERPRISE = 1000;

export type StripePriceIds = {
  starter: string;
  pro: string;
  enterprise: string;
};

/** Resuelve Price IDs públicos (build-time) en el mismo orden que el backend documenta. */
export function resolvePublicStripePriceIds(): StripePriceIds {
  return {
    starter: (
      process.env.NEXT_PUBLIC_STRIPE_PRICE_BASIC ??
      process.env.NEXT_PUBLIC_STRIPE_PRICE_STARTER ??
      process.env.NEXT_PUBLIC_STRIPE_PRICE_COMPLIANCE ??
      process.env.NEXT_PUBLIC_STRIPE_PRICE_ESSENTIAL ??
      ""
    ).trim(),
    pro: (process.env.NEXT_PUBLIC_STRIPE_PRICE_PRO ?? process.env.NEXT_PUBLIC_STRIPE_PRICE_FINANCE ?? "").trim(),
    enterprise: (
      process.env.NEXT_PUBLIC_STRIPE_PRICE_ENTERPRISE ??
      process.env.NEXT_PUBLIC_STRIPE_PRICE_FULL_STACK ??
      ""
    ).trim(),
  };
}

export function stripeCheckoutReady(ids: StripePriceIds): boolean {
  return Boolean(ids.starter && ids.pro && ids.enterprise);
}

/**
 * Matriz de inclusión por fila de comparación (orden = `catalog.landing.pricing.features`).
 * Alineado con `plan_features()` del backend: Essential sin motor financiero avanzado;
 * liquidaciones automáticas como diferencial Enterprise.
 */
export const PLAN_COMPARISON_INCLUDES: Record<PlanSlug, readonly boolean[]> = {
  [PLAN_SLUG_STARTER]: [true, false, true, false, false, false],
  [PLAN_SLUG_PRO]: [true, true, true, true, true, false],
  [PLAN_SLUG_ENTERPRISE]: [true, true, true, true, true, true],
};

export type PublicPlanTier = {
  slug: PlanSlug;
  marketingName: "Essential" | "Pro" | "Enterprise";
  priceEur: number;
  stripePriceId: string;
  includes: readonly boolean[];
  highlight: boolean;
};

export function buildPublicPlanTiers(ids: StripePriceIds): PublicPlanTier[] {
  return [
    {
      slug: PLAN_SLUG_STARTER,
      marketingName: "Essential",
      priceEur: EUR_MONTHLY_ESSENTIAL,
      stripePriceId: ids.starter,
      includes: PLAN_COMPARISON_INCLUDES[PLAN_SLUG_STARTER],
      highlight: false,
    },
    {
      slug: PLAN_SLUG_PRO,
      marketingName: "Pro",
      priceEur: EUR_MONTHLY_PRO,
      stripePriceId: ids.pro,
      includes: PLAN_COMPARISON_INCLUDES[PLAN_SLUG_PRO],
      highlight: true,
    },
    {
      slug: PLAN_SLUG_ENTERPRISE,
      marketingName: "Enterprise",
      priceEur: EUR_MONTHLY_ENTERPRISE,
      stripePriceId: ids.enterprise,
      includes: PLAN_COMPARISON_INCLUDES[PLAN_SLUG_ENTERPRISE],
      highlight: false,
    },
  ];
}

/** Normaliza `?plan=` de la URL a slug canónico (fallback: starter). */
export function normalizePlanQueryParam(raw: string | null | undefined): PlanSlug {
  const s = (raw ?? "").trim().toLowerCase().replace(/-/g, "_");
  if (s === PLAN_SLUG_PRO || s === "finance" || s === "professional") return PLAN_SLUG_PRO;
  if (s === PLAN_SLUG_ENTERPRISE || s === "ent" || s === "full_stack" || s === "fullstack") return PLAN_SLUG_ENTERPRISE;
  if (
    s === PLAN_SLUG_STARTER ||
    s === "compliance" ||
    s === "essential" ||
    s === "basic" ||
    s === "starter" ||
    s === "start"
  ) {
    return PLAN_SLUG_STARTER;
  }
  return PLAN_SLUG_STARTER;
}
