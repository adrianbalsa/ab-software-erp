/** Login, secondary sidebar, quota, customer portal, help hub, common — EN */
export const extraEn = {
  landing: {
    brandAlt: "AB Logistics logo",
    nav: {
      simulator: "Simulator",
      advantage: "Advantage",
      howItWorks: "How it works",
      pricing: "Pricing",
      help: "Help center",
      menuAria: "Menu",
      login: "Sign in",
      requestAccess: "Request system access",
      homeAria: "AB Logistics OS - home",
    },
    hero: {
      eyebrow: "Enterprise logistics OS",
      title: "The fiscal bunker for modern logistics.",
      description:
        "Native VeriFactu compliance, ESG optimization and real-time profitability. Built for CFOs and high-performance fleets.",
      primaryCta: "Request audit",
      secondaryCta: "View architecture",
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
        "Real-time EBITDA",
        "Driver portal",
        "Smart quotation",
        "Expiration control",
        "Automated settlements",
      ],
      title: "Clear pricing",
      subtitle:
        "Monthly investment focused on operational ROI: every euro should return as efficiency and margin control. Indicative figures + VAT; add-ons (OCR, premium webhooks, AI Pro) documented in docs/operations/STRIPE_BILLING.md.",
      recommended: "Recommended",
      connecting: "Connecting...",
      requestAccess: "Request system access",
      missingStripeConfig:
        "Stripe Price IDs are missing in the frontend (NEXT_PUBLIC_STRIPE_PRICE_*). See docs/operations/STRIPE_BILLING.md.",
      stripeGatewayError: "There was a problem connecting to the secure gateway.",
      stripeConnectionError: "Could not connect to the secure gateway. Please try again.",
      pendingUserId: "PENDING_USER_REGISTRATION",
      monthSuffix: "/month",
    },
    faq: {
      title: "Key questions before rolling out AB Logistics OS",
      subtitle: "Strategic answers for finance leadership and fleet operations.",
      items: [
        {
          q: "Is migrating historical records and current fleet data difficult?",
          a: "Not at all. You can import your customer and vehicle database in bulk, or start from scratch by running only new shipments. Our B2B onboarding team can guide you through your first month to ensure a frictionless transition.",
        },
        {
          q: "Is the system worth it if my fleet has fewer than 5 trucks?",
          a: "Absolutely. Small volume does not remove fiscal obligations. Our Compliance plan is designed to shield small fleets for VeriFactu, removing hours of administrative paperwork so you can run your business, not your accounting.",
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
      readyQuestion: "Ready to digitize your fleet?",
      salesCta: "Talk to sales",
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
