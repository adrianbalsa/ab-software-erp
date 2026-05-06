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
        "From quote to cash: fleet, VeriFactu, reconciliation and margin visibility for finance and dispatch. The same commercial offer on the web and in Stripe: Compliance, Operational and Institutional.",
      primaryCta: "Create account and start",
      secondaryCta: "See plans and pricing",
    },
    bento: {
      eyebrow: "Outcomes",
      title: "One platform, four growth levers",
      subtitle:
        "Built for teams that require fiscal traceability, measurable sustainability, and frictionless treasury operations.",
      cards: [
        {
          title: "Compliance without surprises",
          body: "Invoice with confidence and reduce inspection risk without manual, fragile processes.",
        },
        {
          title: "Margin + ESG in one view",
          body: "Spot margin leaks by route while improving footprint with actionable operational decisions.",
        },
        {
          title: "Cash visibility, every week",
          body: "Automate collections and reconciliation to keep treasury under control.",
        },
        {
          title: "Faster decisions",
          body: "Prioritised recommendations for operations, finance and commercial growth.",
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
        "Plans designed to recover margin and cut admin time from month one. Start with the tier that matches your volume and scale without friction.",
      recommended: "Recommended",
      connecting: "Connecting...",
      requestAccess: "Next: sign up and checkout",
      subscribeCta: "Subscribe with Stripe",
      ctaLoginToSubscribe: "Sign in to subscribe",
      contactSalesCta: "Talk to sales",
      limitsFinite: "Up to {{v}} vehicles · up to {{u}} panel users",
      limitsUnlimited: "Unlimited fleet and panel users (Institutional)",
      pricingHelpBillingLink: "Help centre — Billing and Stripe",
      vatExcluded: "VAT excluded",
      missingStripeConfig:
        "Online checkout is temporarily unavailable in this environment. We can enable it for you or send a direct subscription link.",
      pricingStripeFallbackTitle: "Online checkout not enabled yet",
      pricingStripeFallbackBody:
        "Payment links are not active in this environment. You can still review plans and per-plan limits; our sales team can enable checkout or send a subscription link.",
      stripeGatewayError: "There was a problem connecting to the secure gateway.",
      stripeConnectionError: "Could not connect to the secure gateway. Please try again.",
      pendingUserId: "PENDING_USER_REGISTRATION",
      monthSuffix: "/month",
    },
    pricingPage: {
      title: "Subscribe to Compliance, Operational or Institutional",
      subtitle:
        "Choose your plan and activate your subscription in a few steps. If you do not have an account yet, sign up first and continue after onboarding.",
      empresaRequiredHint:
        "Without empresa_id in the URL we cannot attach the charge. After sign-up, open your welcome email link or sign in and go to Subscription.",
      stripeEnvHint:
        "Need help enabling online checkout? Our team can guide setup with you quickly.",
      envVarsList:
        "Prefer support? We can leave subscription live with a short enablement call.",
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
        { value: "ROI", label: "Measured impact on margin, close time and cash visibility" },
        { value: "Stripe", label: "Same Compliance / Operational / Institutional hierarchy in checkout and product" },
      ],
    },
    trustStrip: {
      eyebrow: "Compliance and security",
      title: "Compliance and control for confident growth",
      subtitle:
        "Bring operations, finance and compliance into a single flow to reduce errors, speed up closing and improve management visibility.",
      bullets: [
        {
          title: "Fiscal traceability",
          body: "Invoicing flow aligned with current regulation and clear traceability for audits and accounting teams.",
        },
        {
          title: "Layered security",
          body: "Layered security and company-level data isolation so you can operate safely as volume grows.",
        },
        {
          title: "Transparent billing",
          body: "Stripe Billing with Compliance, Operational and Institutional — same list prices across the product surface.",
        },
      ],
    },
    techSpecs: {
      items: ["VeriFactu compliance ready", "Integrated billing and subscriptions", "Reconciliation and treasury control", "Built to scale with your fleet"],
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
          a: "Absolutely. Small volume does not remove fiscal obligations. The Compliance plan is designed to shield small fleets for VeriFactu, removing hours of administrative paperwork so you can run your business, not your accounting.",
        },
        {
          q: "How exactly does the software guarantee VeriFactu compliance?",
          a: "We help you meet VeriFactu with a guided invoicing flow, clear traceability and audit-ready evidence while reducing manual workload.",
        },
        {
          q: "Are my financial data and customer records secure?",
          a: "Yes. We apply layered security and company-level data isolation so financial and operational information stays protected.",
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
          a: "Yes. You can start small and scale without painful migrations; the product is designed to grow with your shipment volume and process complexity.",
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
          a: "Yes. You can run mixed operations (own fleet + subcontractors), keep visibility by customer/route, and unlock deeper capabilities as complexity increases.",
        },
        {
          q: "What if AEAT changes technical requirements after we subscribe?",
          a: "The product updates as SaaS: when regulation or official schemas evolve, we ship changes in the cloud without you reinstalling servers. Keep your tax advisor in the loop — the software encodes logic aligned with the law in force for each release.",
        },
        {
          q: "Do I have to pay before I know it fits my TMS or accountant?",
          a: "You can sign up, create the company and explore the app with the assigned plan; Stripe checkout aligns when you decide to subscribe (from Subscription or a link that includes empresa_id). If you need specific integrations, Operational and Institutional are the usual tiers for volume and certification.",
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
    starterMsg:
      "Fleet: {used}/5 vehicles. Invoices issued this calendar month: {inv_used}/{inv_limit}. Upgrade to Operational (up to 30 vehicles, no monthly invoice cap).",
    proMsg: "ESG module locked. Upgrade to Institutional to certify your carbon footprint.",
    enterpriseMsg: "Institutional plan · {used} vehicle(s) registered (unlimited).",
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
    themeSystem: "Match system",
    themeAppearance: "Appearance",
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
