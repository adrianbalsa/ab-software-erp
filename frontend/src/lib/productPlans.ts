/**
 * Catálogo público (`./marketingPlanCatalog.ts`) alineado con `backend/app/core/plans.py`.
 * Resolución de Stripe Price IDs en build-time.
 */

import type { StripePriceIds } from "./marketingPlanCatalog";

export type { PublicPlanSlug, PublicPlanTier, StripePriceIds } from "./marketingPlanCatalog";

export {
  PLAN_SLUG_STARTER,
  PLAN_SLUG_PRO,
  PLAN_SLUG_ENTERPRISE,
  EUR_MONTHLY_COMPLIANCE,
  EUR_MONTHLY_FINANCE,
  EUR_MONTHLY_ENTERPRISE,
  PLAN_COMPARISON_INCLUDES,
  buildPublicPlanTiers,
  normalizePlanQueryParam,
} from "./marketingPlanCatalog";

/** Resuelve Price IDs públicos (build-time) en el mismo orden que documenta `STRIPE_BILLING.md`. */
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
