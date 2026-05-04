/**
 * Copia del catálogo en `frontend/src/lib/marketingPlanCatalog.ts`.
 * Mantener alineado manualmente: el deploy de `landing/` en Vercel no incluye `frontend/` ni `shared/`.
 */
export const PLAN_SLUG_STARTER = "starter" as const;
export const PLAN_SLUG_PRO = "pro" as const;
export const PLAN_SLUG_ENTERPRISE = "enterprise" as const;

export type PublicPlanSlug = typeof PLAN_SLUG_STARTER | typeof PLAN_SLUG_PRO | typeof PLAN_SLUG_ENTERPRISE;

/** EUR/mes catálogo (referencia; cargo real = Price en Stripe). Alineado con `plans.py`. */
export const EUR_MONTHLY_COMPLIANCE = 149;
export const EUR_MONTHLY_FINANCE = 449;
export const EUR_MONTHLY_ENTERPRISE = 1200;

/** Máximo de facturas selladas por mes natural en Compliance; debe coincidir con `COMPLIANCE_MAX_FACTURAS_MES` en `plans.py`. */
export const COMPLIANCE_MAX_INVOICES_PER_MONTH = 150;

export type StripePriceIds = {
  starter: string;
  pro: string;
  enterprise: string;
};

/** Inclusión por fila de comparación (misma longitud que `catalog.landing.pricing.features`). */
export const PLAN_COMPARISON_INCLUDES: Record<PublicPlanSlug, readonly boolean[]> = {
  [PLAN_SLUG_STARTER]: [true, false, true, false, false, false],
  [PLAN_SLUG_PRO]: [true, true, true, true, true, false],
  [PLAN_SLUG_ENTERPRISE]: [true, true, true, true, true, true],
} as const;

export type PublicPlanTier = {
  slug: PublicPlanSlug;
  marketingNameEs: "Compliance" | "Operational" | "Institutional";
  marketingNameEn: "Compliance" | "Operational" | "Institutional";
  priceEur: number;
  /** Sufijo opcional tras el precio (p. ej. "+" para catálogo "1.200 €+"). */
  priceSuffix?: string;
  stripePriceId: string;
  includes: readonly boolean[];
  highlight: boolean;
  maxVehicles: number | null;
  maxWorkspaceSeats: number | null;
  limitsLineEs: string;
  limitsLineEn: string;
};

export function buildPublicPlanTiers(ids: StripePriceIds): PublicPlanTier[] {
  return [
    {
      slug: PLAN_SLUG_STARTER,
      marketingNameEs: "Compliance",
      marketingNameEn: "Compliance",
      priceEur: EUR_MONTHLY_COMPLIANCE,
      stripePriceId: ids.starter,
      includes: PLAN_COMPARISON_INCLUDES[PLAN_SLUG_STARTER],
      highlight: false,
      maxVehicles: 5,
      maxWorkspaceSeats: 5,
      limitsLineEs: `Hasta 5 vehículos · hasta 5 usuarios de panel · hasta ${COMPLIANCE_MAX_INVOICES_PER_MONTH} facturas/mes`,
      limitsLineEn: `Up to 5 fleet vehicles · up to 5 panel users · up to ${COMPLIANCE_MAX_INVOICES_PER_MONTH} invoices/mo`,
    },
    {
      slug: PLAN_SLUG_PRO,
      marketingNameEs: "Operational",
      marketingNameEn: "Operational",
      priceEur: EUR_MONTHLY_FINANCE,
      stripePriceId: ids.pro,
      includes: PLAN_COMPARISON_INCLUDES[PLAN_SLUG_PRO],
      highlight: true,
      maxVehicles: 30,
      maxWorkspaceSeats: 30,
      limitsLineEs: "Hasta 30 vehículos en flota · hasta 30 usuarios de panel",
      limitsLineEn: "Up to 30 fleet vehicles · up to 30 panel users",
    },
    {
      slug: PLAN_SLUG_ENTERPRISE,
      marketingNameEs: "Institutional",
      marketingNameEn: "Institutional",
      priceEur: EUR_MONTHLY_ENTERPRISE,
      priceSuffix: "+",
      stripePriceId: ids.enterprise,
      includes: PLAN_COMPARISON_INCLUDES[PLAN_SLUG_ENTERPRISE],
      highlight: false,
      maxVehicles: null,
      maxWorkspaceSeats: null,
      limitsLineEs: "Flota y usuarios de panel ilimitados · ESG, API y acompañamiento enterprise",
      limitsLineEn: "Unlimited fleet and panel users · ESG, APIs and enterprise support",
    },
  ];
}

/** Textos cortos para la app `landing/` (marketing estático). */
export const PLAN_PITCH_I18N: Record<
  PublicPlanSlug,
  { descriptionEs: string; descriptionEn: string; bulletsEs: readonly string[]; bulletsEn: readonly string[] }
> = {
  [PLAN_SLUG_STARTER]: {
    descriptionEs: "Duerma tranquilo con la AEAT: VeriFactu, QR y firma XAdES-BES.",
    descriptionEn: "Sleep soundly with AEAT compliance: VeriFactu, QR and XAdES-BES signing.",
    bulletsEs: [
      "Facturación con encadenamiento VeriFactu",
      "Almacenamiento cifrado de facturas (4 años legales)",
      `Hasta 5 vehículos, 5 usuarios de panel y ${COMPLIANCE_MAX_INVOICES_PER_MONTH} facturas/mes`,
      "Sustituye Excel o ERP desactualizado frente a la normativa",
    ],
    bulletsEn: [
      "Invoicing with VeriFactu chaining",
      "Encrypted invoice storage (4-year retention)",
      `Up to 5 vehicles, 5 panel users and ${COMPLIANCE_MAX_INVOICES_PER_MONTH} invoices/mo`,
      "Replaces spreadsheets or outdated ERPs for 2026 rules",
    ],
  },
  [PLAN_SLUG_PRO]: {
    descriptionEs: "Optimice su margen operativo: combustible, EBITDA en tiempo real y LogisAdvisor.",
    descriptionEn: "Optimize operating margin: fuel, real-time EBITDA and LogisAdvisor.",
    bulletsEs: [
      "Módulo de combustible y telemetría (radar de fugas)",
      "Dashboards de EBITDA y rentabilidad por ruta",
      "LogisAdvisor (IA) para análisis operativo",
      "RBAC y hasta 30 vehículos / 30 usuarios de panel",
    ],
    bulletsEn: [
      "Fuel module and telemetry (leak/theft radar)",
      "EBITDA dashboards and route profitability",
      "LogisAdvisor (AI) for operational analysis",
      "RBAC and up to 30 vehicles / 30 panel users",
    ],
  },
  [PLAN_SLUG_ENTERPRISE]: {
    descriptionEs: "Liderazgo en ESG y seguridad: certificación CO₂ (Euro VI / ISO 14083) y armadura corporativa.",
    descriptionEn: "ESG and security leadership: CO₂ certification (Euro VI / ISO 14083) and corporate-grade controls.",
    bulletsEs: [
      "Módulo ESG-CO₂ para licitaciones y grandes contratos",
      "Data Security Pro: auditoría, cifrado y API/webhooks",
      "SLA de respuesta en menos de 4 h y Account Manager dedicado",
      "Paquetes de auditoría listos para Due Diligence",
    ],
    bulletsEn: [
      "ESG-CO₂ module for tenders and large contracts",
      "Data Security Pro: audit logs, encryption and API/webhooks",
      "Under 4h SLA response and a dedicated account manager",
      "Audit packs ready for due diligence",
    ],
  },
};

export function normalizePlanQueryParam(raw: string | null | undefined): PublicPlanSlug {
  const s = (raw ?? "").trim().toLowerCase().replace(/-/g, "_");
  if (
    s === PLAN_SLUG_PRO ||
    s === "finance" ||
    s === "professional" ||
    s === "operational" ||
    s === "operations"
  ) {
    return PLAN_SLUG_PRO;
  }
  if (
    s === PLAN_SLUG_ENTERPRISE ||
    s === "ent" ||
    s === "full_stack" ||
    s === "fullstack" ||
    s === "institutional" ||
    s === "enterprise"
  ) {
    return PLAN_SLUG_ENTERPRISE;
  }
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
