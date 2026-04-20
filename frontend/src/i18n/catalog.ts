import { extraEn } from "./extra.en";
import { extraEs } from "./extra.es";
import { pagesEn } from "./pages.en";
import { pagesEs } from "./pages.es";
import { shellEn } from "./shell.en";
import { shellEs } from "./shell.es";

export type AppLocale = "es" | "en";

export type Catalog = {
  appShell: typeof shellEs;
  sidebar: typeof extraEs.sidebar;
  login: typeof extraEs.login;
  quota: typeof extraEs.quota;
  common: typeof extraEs.common;
  portalCliente: typeof extraEs.portalCliente;
  helpHub: typeof extraEs.helpHub;
  nav: {
    billing: string;
    billingSub: string;
    help: string;
    helpSub: string;
    pricing: string;
    appLogin: string;
  };
  locale: { es: string; en: string; label: string };
  pricing: {
    title: string;
    subtitle: string;
    loginCta: string;
    perMonth: string;
    starterName: string;
    starterPrice: string;
    starterDesc: string;
    starterBullets: readonly string[];
    proName: string;
    proPrice: string;
    proDesc: string;
    proBullets: readonly string[];
    entName: string;
    entPrice: string;
    entDesc: string;
    entBullets: readonly string[];
    choose: string;
    currentNote: string;
    checkoutCancelled: string;
  };
  helpIndex: {
    title: string;
    subtitle: string;
    billingCard: string;
    billingDesc: string;
    open: string;
  };
  helpBilling: {
    title: string;
    back: string;
    md: string;
  };
  billingPage: {
    title: string;
    subtitle: string;
    planLabel: string;
    usageLabel: string;
    portalCta: string;
    portalHint: string;
    upgradePro: string;
    upgradeEnt: string;
    loadingPortal: string;
    portalDisabled: string;
    errorPrefix: string;
    refresh: string;
  };
  pages: typeof pagesEs;
};

const pricingEs = {
  title: "Planes y precios",
  subtitle:
    "Elige el plan que encaja con tu flota. Los cobros se gestionan de forma segura con Stripe Billing.",
  loginCta: "Iniciar sesión para contratar",
  perMonth: "/mes + IVA",
  starterName: "Compliance",
  starterPrice: "39 €",
  starterDesc: "Hasta 5 vehículos, VeriFactu y operativa central (catálogo 2026).",
  starterBullets: [
    "VeriFactu y facturación electrónica",
    "Cuadro de mando operativo",
    "Límite de 5 vehículos en flota",
  ],
  proName: "Finance",
  proPrice: "149 €",
  proDesc: "Hasta 25 vehículos y motor financiero avanzado.",
  proBullets: [
    "Todo lo de Compliance",
    "Hasta 25 vehículos",
    "Inteligencia financiera y BI ampliado",
  ],
  entName: "Full-Stack",
  entPrice: "449 €",
  entDesc: "Flota ilimitada, ESG comercial y certificación.",
  entBullets: [
    "Todo lo de Finance",
    "Flota sin límite",
    "Módulo ESG y certificados auditables",
  ],
  choose: "Contratar",
  currentNote:
    "Si ya tienes cuenta, inicia sesión y usa «Mejorar plan» en el panel o la página de Suscripción.",
  checkoutCancelled: "Has cancelado el checkout. Puedes elegir otro plan cuando quieras.",
} as const;

const pricingEn = {
  title: "Plans & pricing",
  subtitle: "Pick the plan that matches your fleet. Billing is handled securely with Stripe Billing.",
  loginCta: "Sign in to subscribe",
  perMonth: "/month + VAT",
  starterName: "Compliance",
  starterPrice: "€39",
  starterDesc: "Up to 5 vehicles, VeriFactu and core operations (2026 catalog).",
  starterBullets: [
    "VeriFactu & e-invoicing",
    "Operational dashboard",
    "Fleet cap of 5 vehicles",
  ],
  proName: "Finance",
  proPrice: "€149",
  proDesc: "Up to 25 vehicles and advanced financial intelligence.",
  proBullets: ["Everything in Compliance", "Up to 25 vehicles", "Extended BI & finance engine"],
  entName: "Full-Stack",
  entPrice: "€449",
  entDesc: "Unlimited fleet, commercial ESG and certification.",
  entBullets: ["Everything in Finance", "Unlimited fleet", "ESG module & auditable certificates"],
  choose: "Subscribe",
  currentNote:
    "If you already have an account, sign in and use “Upgrade plan” in the sidebar or the Subscription page.",
  checkoutCancelled: "Checkout was cancelled. You can pick a plan again anytime.",
} as const;

const helpBillingMdEs = `
Los pagos del **plan SaaS** (**Compliance**, **Finance**, **Full-Stack**; slugs \`starter\` / \`pro\` / \`enterprise\`) se procesan con **Stripe** en modo suscripción recurrente. Precios de catálogo orientativos: **39 €**, **149 €** y **449 €** / mes (+ IVA según caso).

### Add-ons (referencia comercial)
| Add-on | Precio orientativo |
|--------|-------------------|
| OCR Pack (documentos extra) | 15 € / mes |
| Webhooks B2B Premium | 49 € / mes |
| LogisAdvisor IA Pro | 29 € / mes |

Los \`price_*\` reales se configuran en Stripe Dashboard y variables \`STRIPE_PRICE_*\` (ver \`docs/operations/STRIPE_BILLING.md\`).

### Contratar o cambiar de plan
1. Inicia sesión con un usuario administrador de tu empresa.
2. Desde **Suscripción** en el menú, o desde la tarjeta de cuota, inicia el checkout.
3. Tras el pago, Stripe envía un evento al backend que actualiza tu plan y límites de flota.

### Portal de facturación
Si ya completaste un checkout, puedes abrir el **portal de cliente de Stripe** para actualizar la tarjeta, descargar facturas o cancelar la renovación. Si ves un error de «sin cliente Stripe», completa primero un checkout.

### Webhooks e idempotencia
El endpoint canónico recibe eventos firmados. Las entregas duplicadas del mismo \`evt_*\` no reaplican cambios (idempotencia en base de datos).

### Soporte
Para incidencias de acceso o datos de transporte, contacta con el administrador de tu tenant o con soporte según tu contrato.
`.trim();

const helpBillingMdEn = `
**SaaS plan** charges (**Compliance**, **Finance**, **Full-Stack**; slugs \`starter\` / \`pro\` / \`enterprise\`) are processed by **Stripe** as recurring subscriptions. Indicative list prices: **€39**, **€149** and **€449** / month (+ VAT as applicable).

### Add-ons (commercial reference)
| Add-on | Indicative price |
|--------|------------------|
| OCR Pack (extra documents) | €15 / month |
| Webhooks B2B Premium | €49 / month |
| LogisAdvisor IA Pro | €29 / month |

Real \`price_*\` IDs are configured in Stripe Dashboard and \`STRIPE_PRICE_*\` env vars (see \`docs/operations/STRIPE_BILLING.md\`).

### Subscribe or change plan
1. Sign in with an **admin** user for your company.
2. From **Subscription** in the sidebar, or the quota card, start checkout.
3. After payment, Stripe notifies the backend to update your plan and fleet limits.

### Billing portal
Once checkout has completed at least once, open the **Stripe customer portal** to update your card, download invoices or cancel renewal. If you see “no Stripe customer”, complete checkout first.

### Webhooks & idempotency
The canonical endpoint receives signed events. Duplicate deliveries of the same \`evt_*\` do not re-apply side effects (database idempotency).

### Support
For access issues or transport data, contact your tenant admin or support as per your agreement.
`.trim();

const es: Catalog = {
  appShell: shellEs,
  ...extraEs,
  nav: {
    billing: "Suscripción",
    billingSub: "Stripe Billing",
    help: "Centro de ayuda",
    helpSub: "Facturación y autoservicio",
    pricing: "Precios",
    appLogin: "Acceso clientes",
  },
  locale: { es: "ES", en: "EN", label: "Idioma" },
  pricing: pricingEs,
  helpIndex: {
    title: "Centro de ayuda",
    subtitle: "Respuestas rápidas sobre facturación, Stripe y tu cuenta.",
    billingCard: "Facturación y Stripe",
    billingDesc: "Cómo funciona la suscripción, el portal de cliente y las renovaciones.",
    open: "Ver artículo",
  },
  helpBilling: {
    title: "Facturación con Stripe",
    back: "Volver al centro de ayuda",
    md: helpBillingMdEs,
  },
  billingPage: {
    title: "Suscripción y facturación",
    subtitle: "Gestiona tu plan SaaS y el método de pago a través de Stripe.",
    planLabel: "Plan actual",
    usageLabel: "Uso de flota",
    portalCta: "Abrir portal de facturación (Stripe)",
    portalHint:
      "Te redirigimos a Stripe para tarjeta, facturas PDF y cancelación de renovación. Volverás al panel al cerrar.",
    upgradePro: "Contratar o pasar a Finance",
    upgradeEnt: "Contratar Full-Stack",
    loadingPortal: "Abriendo portal…",
    portalDisabled: "Completa antes un checkout para asociar un cliente Stripe a tu empresa.",
    errorPrefix: "No se pudo abrir el portal",
    refresh: "Actualizar",
  },
  pages: pagesEs,
};

const en = {
  appShell: shellEn as unknown as typeof shellEs,
  ...extraEn,
  nav: {
    billing: "Subscription",
    billingSub: "Stripe Billing",
    help: "Help center",
    helpSub: "Billing & self-service",
    pricing: "Pricing",
    appLogin: "Customer login",
  },
  locale: { es: "ES", en: "EN", label: "Language" },
  pricing: pricingEn,
  helpIndex: {
    title: "Help center",
    subtitle: "Quick answers on billing, Stripe and your workspace.",
    billingCard: "Billing & Stripe",
    billingDesc: "How subscriptions work, the customer portal and renewals.",
    open: "Read article",
  },
  helpBilling: {
    title: "Billing with Stripe",
    back: "Back to help center",
    md: helpBillingMdEn,
  },
  billingPage: {
    title: "Subscription & billing",
    subtitle: "Manage your SaaS plan and payment method via Stripe.",
    planLabel: "Current plan",
    usageLabel: "Fleet usage",
    portalCta: "Open billing portal (Stripe)",
    portalHint:
      "You will be redirected to Stripe for card, PDF invoices and renewal cancellation. You return to the app when finished.",
    upgradePro: "Subscribe or upgrade to Finance",
    upgradeEnt: "Subscribe to Full-Stack",
    loadingPortal: "Opening portal…",
    portalDisabled: "Complete checkout once so a Stripe customer is linked to your company.",
    errorPrefix: "Could not open portal",
    refresh: "Refresh",
  },
  pages: pagesEn as unknown as typeof pagesEs,
} as unknown as Catalog;

export const catalogs: Record<AppLocale, Catalog> = { es, en };

export function pickLocale(raw: string | null | undefined): AppLocale {
  const s = (raw || "").trim().toLowerCase();
  return s === "en" ? "en" : "es";
}
