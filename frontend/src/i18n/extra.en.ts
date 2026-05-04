/** Login, secondary sidebar, quota, customer portal, help hub, common — EN */
export const extraEn = {
  landing: {
    brandAlt: "AB Logistics logo",
    nav: {
      simulator: "Simulator",
      advantage: "Advantage",
      howItWorks: "How it works",
      platform: "Product",
      trust: "Trust",
      pricing: "Pricing",
      help: "Help center",
      menuAria: "Menu",
      login: "Sign in",
      requestAccess: "Request system access",
      homeAria: "AB Logistics OS - home",
    },
    hero: {
      eyebrow: "Transport · Finance · AEAT 2026",
      title: "One platform for profitable shipments and inspection-ready invoicing.",
      description:
        "From quote to cash: fleet, VeriFactu, reconciliation and margin visibility for finance and dispatch. The same commercial offer on the web and in Stripe: Essential, Pro and Enterprise.",
      primaryCta: "Create account and start",
      secondaryCta: "See plans and pricing",
    },
    bento: {
      eyebrow: "Architecture",
      title: "One platform, four advantages",
      subtitle:
        "Built for teams that require fiscal traceability, measurable sustainability, and frictionless treasury operations.",
      cards: [
        {
          title: "Fiscal hardening (VeriFactu)",
          body: "XAdES-BES signature and chained hashes. 100% compliant with Spain's anti-fraud regulation.",
        },
        {
          title: "CIP & ESG matrix",
          body: "GLEC algorithm to align operational margin with carbon footprint reduction.",
        },
        {
          title: "Bank reconciliation",
          body: "Native Stripe and GoCardless integrations to automate cashflow.",
        },
        {
          title: "Autonomous intelligence (Roadmap)",
          body: "Future-ready with LogisAdvisor (AI) and dynamic routing powered by Google Maps.",
        },
      ],
    },
    pricing: {
      features: [
        "VeriFactu certification",
        "Advanced finance / EBITDA engine",
        "Driver portal",
        "Smart quotation",
        "Expiration control",
        "Automated settlements",
      ],
      title: "Published plans = Stripe plans",
      subtitle:
        "Three tiers with the same names in product and billing: Essential (€350), Pro (€800) and Enterprise (€1000) per month + VAT. Optional add-ons (OCR Pack, Webhooks B2B Premium, LogisAdvisor IA Pro) are purchased from the app.",
      recommended: "Recommended",
      connecting: "Connecting...",
      requestAccess: "Next: sign up and checkout",
      subscribeCta: "Subscribe with Stripe",
      vatExcluded: "VAT excluded",
      missingStripeConfig:
        "Stripe Price IDs are missing in the frontend (NEXT_PUBLIC_STRIPE_PRICE_*). See docs/operations/STRIPE_BILLING.md.",
      pricingStripeFallbackTitle: "Online checkout unavailable",
      pricingStripeFallbackBody:
        "Payment links are not configured in this environment. You can still review the plans below; to subscribe, contact sales or finish Stripe setup.",
      stripeGatewayError: "There was a problem connecting to the secure gateway.",
      stripeConnectionError: "Could not connect to the secure gateway. Please try again.",
      pendingUserId: "PENDING_USER_REGISTRATION",
      monthSuffix: "/month",
    },
    pricingPage: {
      title: "Subscribe to Essential, Pro or Enterprise",
      subtitle:
        "List prices aligned with the backend and Stripe Billing. If you do not have an empresa_id yet, create your account, finish onboarding and return here or use Subscription in the app.",
      empresaRequiredHint:
        "Without empresa_id in the URL we cannot attach the charge. After sign-up, open your welcome email link or sign in and go to Subscription.",
      stripeEnvHint:
        "Your build must define all three NEXT_PUBLIC_STRIPE_PRICE_* values (Essential via BASIC or STARTER, PRO, ENTERPRISE).",
      envVarsList:
        "Example: NEXT_PUBLIC_STRIPE_PRICE_BASIC or NEXT_PUBLIC_STRIPE_PRICE_STARTER, NEXT_PUBLIC_STRIPE_PRICE_PRO, NEXT_PUBLIC_STRIPE_PRICE_ENTERPRISE.",
      funnelHint:
        "Self-serve flow: sign up → company created → Stripe checkout from this page (with ?empresa_id=) or from the Subscription menu.",
      loginCta: "Sign in to pay",
      backHome: "Back to public site",
      headerLogin: "Customer login",
    },
    socialProof: {
      eyebrow: "Why dispatch teams take a second look",
      title: "Less manual closing. More control before margin leaks.",
      subtitle:
        "Built for carriers that already invoice at scale and cannot afford to duplicate data across spreadsheets, ERP and the accountant’s inbox.",
      stats: [
        { value: "VeriFactu", label: "Fiscal logging focused on traceability and integrity" },
        { value: "RLS", label: "Each tenant isolated at the database layer" },
        { value: "Stripe", label: "Same plan hierarchy in checkout and internal docs" },
      ],
    },
    trustStrip: {
      eyebrow: "Compliance and security",
      title: "VeriFactu: hash chains and operational discipline",
      subtitle:
        "Product priority is fiscal record integrity and coherence between operations and billing. No shortcuts that weaken an inspection story.",
      bullets: [
        {
          title: "Fiscal traceability",
          body: "Designed for chained records and e-invoicing requirements; QR and submission flows when regulation applies.",
        },
        {
          title: "Layered security",
          body: "TLS in transit, PostgreSQL RLS per company and secret handling aligned with best practices (no credentials in code).",
        },
        {
          title: "Transparent billing",
          body: "Stripe Billing with Essential, Pro and Enterprise — same names and indicative prices across the product surface.",
        },
      ],
    },
    techSpecs: {
      items: ["VeriFactu-ready", "TLS + RLS PostgreSQL", "Stripe Billing", "GoCardless / SEPA"],
    },
    faq: {
      title: "Key questions before rolling out AB Logistics OS",
      subtitle: "Typical transport, dispatch and finance objections — without marketing fluff.",
      items: [
        {
          q: "Is migrating historical records and current fleet data difficult?",
          a: "Not at all. You can import your customer and vehicle database in bulk, or start from scratch by running only new shipments. Our B2B onboarding team can guide you through your first month to ensure a frictionless transition.",
        },
        {
          q: "Is the system worth it if my fleet has fewer than 5 trucks?",
          a: "Absolutely. Small volume does not remove fiscal obligations. Our Essential plan is designed to shield small fleets for VeriFactu, removing hours of administrative paperwork so you can run your business, not your accounting.",
        },
        {
          q: "How exactly does the software guarantee VeriFactu compliance?",
          a: "We operate like a fiscal bunker. The AB Logistics OS engine automatically chains invoice hashes, issues the mandatory QR code, guarantees immutable records, and is ready for automatic submission to AEAT.",
        },
        {
          q: "Are my financial data and customer records secure?",
          a: "Security is banking-grade. We use AES-128 encryption for sensitive data and strict PostgreSQL Row Level Security (RLS). At the database level, this makes it physically impossible for one customer to access another customer's data.",
        },
        {
          q: "Does the system integrate with my banks for reconciliation and collections?",
          a: "Yes. AB Logistics OS is designed to integrate with institutional gateways such as GoCardless and Stripe, automating SEPA direct debits and invoice reconciliation so your cash flow is always up to date.",
        },
        {
          q: "How do you automate carbon footprint reporting (ESG)?",
          a: "Our engine crosses route data with fleet certifications (for example, Euro VI). This produces precise, audit-ready emissions reports, which large multinationals increasingly require from logistics providers.",
        },
        {
          q: "If my company grows fast, can the software keep up?",
          a: "AB Logistics OS is cloud-native with a serverless architecture that scales dynamically. Whether you manage 10 shipments a month or 10,000, system performance in the Enterprise plan remains consistent with no latency bottlenecks.",
        },
        {
          q: "What level of technical support is included in the subscription?",
          a: "We provide specialized support. No bots; your team has direct access to technical support for operational questions, integrations, and guidance on the platform's fiscal logic.",
        },
        {
          q: "Are there lock-in contracts or hidden implementation fees?",
          a: "Transparency is a core principle. We do not charge setup fees and do not require long-term lock-in contracts. It is pure SaaS: pay monthly (or discounted annually) and cancel whenever you decide.",
        },
        {
          q: "Can I test the platform before committing my company's operations?",
          a: "We know switching ERP is a critical decision. We offer tailored demo sessions and the option to run a controlled pilot so your CFO can validate the platform before full rollout.",
        },
        {
          q: "Will drivers refuse yet another app?",
          a: "The driver portal targets short flows (shipment status, delivery, paperwork). You can start with dispatch and billing, then expand to the field when you see value. It does not replace the tachograph or driving-time rules — it complements the documentary and commercial side of the shipment.",
        },
        {
          q: "What about CMR, PODs and evidence if there is a claim or a customer dispute?",
          a: "We centralise case traceability (origin, destination, price, linked documents) so dispatch and admin work from one source of truth. Civil and commercial liability still sits with the carriage and contract; the software reduces transcription errors and documentation gaps.",
        },
        {
          q: "We use subcontractors and agencies — does it work for mixed fleets?",
          a: "Yes. Multi-tenant architecture and roles are designed so each company only sees its own world (RLS). You can model customers, recurring routes and internal ops; for complex subcontract chains, Pro and Enterprise add analytics and certification depth.",
        },
        {
          q: "What if AEAT changes technical requirements after we subscribe?",
          a: "The product updates as SaaS: when regulation or official schemas evolve, we ship changes in the cloud without you reinstalling servers. Keep your tax advisor in the loop — the software encodes logic aligned with the law in force for each release.",
        },
        {
          q: "Do I have to pay before I know it fits my TMS or accountant?",
          a: "You can sign up, create the company and explore the app with the assigned plan; Stripe checkout aligns when you decide to subscribe (from Subscription or a link that includes empresa_id). If you need specific integrations, Pro and Enterprise are the usual tiers for volume and certification.",
        },
      ],
    },
    footer: {
      description: "Operating system for fleets, finance, and fiscal compliance.",
      legal: "Legal",
      legalNotice: "Legal notice",
      privacy: "Privacy policy (GDPR)",
      cookies: "Cookies policy",
      terms: "Terms and conditions",
      contact: "Contact",
      readyQuestion: "Already have an account?",
      salesCta: "Sign in",
      copyright: "All rights reserved.",
    },
    moats: {
      title: "Operational hardening capabilities",
      subtitle:
        "Capabilities designed to maximize returns: more control, less margin leakage, and finance-driven decisions.",
      capabilities: [
        {
          title: "VeriFactu certification",
          description: "Fiscal traceability chain and compliance readiness for AEAT 2026 inspections.",
        },
        {
          title: "Real-time EBITDA",
          description: "Instant financial visibility by route, customer and vehicle to decide with real margin data.",
        },
        {
          title: "Driver portal",
          description: "Centralized field operations for records, statuses and communication without friction.",
        },
        {
          title: "Smart quotation",
          description: "Faster, more consistent budgets based on real costs, history and business rules.",
        },
        {
          title: "Expiration control",
          description: "Unified alerts for documents, inspections and critical fleet obligations.",
        },
        {
          title: "Automated settlements",
          description: "Settlement calculation and closure with fewer errors and shorter admin cycles.",
        },
      ],
    },
    howItWorks: {
      title: "How it works",
      subtitle: "Onboarding designed for operators, not consultants.",
      stepLabel: "Step",
      steps: [
        {
          title: "Add your fleet and fixed costs",
          desc: "Configure vehicles and cost structure in just over a minute.",
          time: "~1 min",
        },
        {
          title: "Register a shipment",
          desc: "From cab or office: origin, destination and price in seconds.",
          time: "~30 sec",
        },
        {
          title: "The system does the rest",
          desc: "Invoices, margin, VeriFactu and CO₂ are calculated automatically.",
          time: "Automatic",
        },
      ],
    },
    roi: {
      title: "Interactive ROI simulator",
      subtitle: "Adjust your fleet and average mileage. Results update instantly.",
      fleetSize: "Your fleet size",
      trucksSuffix: "trucks",
      fleetRangeHint: "Between 1 and 50 trucks",
      kmPerTruck: "Average kilometers per truck / month",
      kmRangeHint: "500 - 12,000 km",
      adminSaved: "Administrative time saved",
      adminSavedHint: "Estimate: 4 h per truck in administrative tasks",
      economicSaving: "Estimated cost savings",
      economicSavingHint: "Reference hourly value: €25",
      trackedEsg: "Tracked ESG footprint",
      trackedEsgHint: "Model: km × 0.085 kg CO₂ (indicative)",
      hoursPerMonth: "h/month",
      kgPerMonth: "kg CO₂ / month",
      monthSuffix: "/month",
      summaryPrefix: "Recover",
      summarySuffix: "per month. Your subscription pays for itself.",
    },
    heroLegacy: {
      trustSignals: ["Support in Spain", "Onboarding in 24h", "Adapted to VeriFactu 2026"],
      pill: "B2B platform · Transport and logistics",
      titlePrefix: "The definitive operating system for",
      titleHighlight: "Smart fleets",
      description:
        "Operational margin optimization (EBITDA), VeriFactu 2026 compliance and financial traceability in one control system for management.",
      primaryCta: "Audit my fleet",
      secondaryCta: "View demo",
      complianceNote: "Ready for AEAT 2026 regulation (Ley Crea y Crece)",
    },
  },
  sidebar: {
    developerApi: "API & Webhooks",
    developerApiSub: "Keys & endpoints",
    logout: "Sign out",
    demoMode: "Demo mode",
    roleLabels: {
      owner: "Owner",
      admin: "Administrator",
      traffic_manager: "Traffic manager",
      driver: "Driver",
      cliente: "Customer",
      developer: "Developer",
    } as const,
  },
  login: {
    tagline: "Sign in to your company workspace",
    username: "Username",
    email: "Email",
    password: "Password",
    forgotPassword: "Forgot your password?",
    forgotPasswordTitle: "Reset your password",
    forgotPasswordSubtitle:
      "Enter your account email. If an account exists, we'll send you a link to reset your password.",
    sendInstructions: "Send instructions",
    checkEmailInbox:
      "If that email is registered in our system, you'll receive a recovery link shortly.",
    emailSentTitle: "Email sent",
    forgotPasswordBackToLogin: "Back to sign in",
    forgotPasswordEmailRequired: "Please enter a valid email address.",
    forgotPasswordGenericError: "We could not complete the request. Please try again later.",
    submit: "Sign in",
    submitShort: "Sign in",
    pending: "Signing in…",
    pendingShort: "Signing in...",
    oauthDivider: "or continue with",
    google: "Google",
    googlePending: "Connecting...",
    backToMarketing: "Back to public site",
    oauthFail: "Could not sign in with Google.",
    supabasePending: "Supabase configuration is pending.",
  },
  quota: {
    noData: "No quota data",
    quotaPrefix: "Quota:",
    fleetQuota: "Fleet quota",
    starterMsg: "You are using {used} of 5 vehicles. Upgrade to PRO for up to 25.",
    proMsg: "ESG module locked. Upgrade to ENTERPRISE to certify your carbon footprint.",
    enterpriseMsg: "Enterprise plan · {used} vehicle(s) registered (unlimited).",
    upgrade: "Upgrade plan",
    manageSubscription: "Manage subscription",
    manageSubscriptionBusy: "Opening billing portal…",
    helpQuotaBilling: "Help: plans & billing (Stripe)",
  },
  common: {
    loadingEllipsis: "Loading…",
    configPendingTitle: "Configuration pending",
    configPendingBody:
      "The system is temporarily unavailable. Supabase configuration must be completed.",
  },
  portalCliente: {
    badge: "Shipper portal",
    mobileHeader: "Customer portal",
    themeLight: "Light mode",
    themeDark: "Dark mode",
    signOut: "Sign out",
    navShipments: "My shipments",
    navInvoices: "Invoices",
    navEsg: "ESG sustainability",
    navBi: "Live BI",
    footer: {
      help: "Help centre",
      privacy: "Privacy (GDPR)",
      legal: "Legal notice",
      support: "Contact / support",
      apiDebugPrefix: "API · ",
      productNote: "VeriFactu, ESG and billing per your commercial agreement.",
    },
  },
  helpHub: {
    hubTitle: "Help center",
    hubSubtitle:
      "Commercial documentation, Stripe billing, security, compliance and operations. Search by keyword or filter by category.",
    searchPlaceholder: "Search titles and excerpts…",
    searchLabel: "Search articles",
    allCategories: "All",
    noResults: "No articles match your search.",
    readArticle: "Read article",
    footerLegal:
      "Contractual legal texts (SLA, privacy) are provided under your commercial agreement. For technical compliance posture, use the public compliance API.",
    footerPricing: "View plans",
    footerLogin: "Sign in to ERP",
    updatedLabel: "Updated",
    categories: {
      onboarding: "Getting started",
      billing: "Billing & Stripe",
      security: "Security & data",
      compliance: "Compliance & AEAT",
      integrations: "Integrations",
      support: "Support & SLA",
    },
  },
} as const;
