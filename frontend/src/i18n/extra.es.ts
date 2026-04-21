/** Login, sidebar secundario, cuota, portal cliente, ayuda hub, comunes — ES */
export const extraEs = {
  landing: {
    brandAlt: "Logo de AB Logistics",
    nav: {
      simulator: "Simulador",
      advantage: "Ventaja",
      howItWorks: "Cómo funciona",
      pricing: "Precios",
      help: "Centro de ayuda",
      menuAria: "Menú",
      login: "Iniciar sesión",
      requestAccess: "Solicitar acceso al sistema",
      homeAria: "AB Logistics OS - inicio",
    },
    hero: {
      eyebrow: "Enterprise logistics OS",
      title: "El Búnker Fiscal para la Logística Moderna.",
      description:
        "Cumplimiento VeriFactu nativo, optimización ESG y rentabilidad en tiempo real. Construido para CFOs y flotas de alto rendimiento.",
      primaryCta: "Solicitar auditoría",
      secondaryCta: "Ver arquitectura",
    },
    bento: {
      eyebrow: "Arquitectura",
      title: "Una plataforma, cuatro ventajas",
      subtitle:
        "Diseñada para equipos que exigen trazabilidad fiscal, sostenibilidad medible y tesorería sin fricción.",
      cards: [
        {
          title: "Blindaje fiscal (VeriFactu)",
          body: "Firma XAdES-BES y encadenamiento de hashes. 100% compliant con la Ley Antifraude de la AEAT.",
        },
        {
          title: "Matriz CIP & ESG",
          body: "Algoritmo GLEC para alinear el margen operativo con la reducción de la huella de carbono.",
        },
        {
          title: "Reconciliación bancaria",
          body: "Integración nativa con Stripe y GoCardless para automatizar el cashflow.",
        },
        {
          title: "Inteligencia autónoma (Roadmap)",
          body: "Preparado para el futuro con LogisAdvisor (IA) y enrutamiento dinámico mediante Google Maps.",
        },
      ],
    },
    pricing: {
      features: [
        "Certificación VeriFactu",
        "EBITDA en tiempo real",
        "Portal del chófer",
        "Cotizador inteligente",
        "Control de vencimientos",
        "Liquidaciones automáticas",
      ],
      title: "Precios claros",
      subtitle:
        "Inversión mensual orientada a ROI operativo: cada euro debe volver en eficiencia y control de margen. Cifras orientativas + IVA; add-ons (OCR, webhooks premium, IA Pro) documentados en docs/operations/STRIPE_BILLING.md.",
      recommended: "Recomendado",
      connecting: "Conectando...",
      requestAccess: "Solicitar acceso al sistema",
      missingStripeConfig:
        "Falta configurar los Price IDs de Stripe en el frontend (NEXT_PUBLIC_STRIPE_PRICE_*). Consulta docs/operations/STRIPE_BILLING.md.",
      stripeGatewayError: "Hubo un problema al conectar con la pasarela segura.",
      stripeConnectionError: "No se pudo conectar con la pasarela segura. Inténtalo de nuevo.",
      pendingUserId: "USUARIO_PENDIENTE_DE_REGISTRO",
      monthSuffix: "/mes",
    },
    faq: {
      title: "Preguntas frecuentes",
      subtitle: "Respuestas directas antes de dar el siguiente paso.",
      items: [
        {
          q: "¿Es difícil migrar mis datos actuales?",
          a: "No. Puedes importar clientes y flota de forma guiada, o empezar cargando solo portes y facturas nuevas. Nuestro equipo puede ayudarte en el primer mes si lo necesitas.",
        },
        {
          q: "¿Qué pasa si tengo menos de 5 camiones?",
          a: "El plan Compliance (pequeña flota) está pensado para autónomos y operadores con hasta 5 vehículos y VeriFactu completo. Sin penalización por ser pequeño.",
        },
        {
          q: "¿Cómo garantiza el software la ley VeriFactu?",
          a: "Cada factura genera un hash criptográfico encadenado con el registro anterior. Los datos son inmutables tras emitirse: la trazabilidad cumple los requisitos de la normativa AEAT y el SIF.",
        },
        {
          q: "¿Puedo probar antes de comprometerme?",
          a: "Sí. Puedes solicitar acceso al sistema para auditar tu operativa con dashboard y simuladores, sin fricción en el primer paso.",
        },
      ],
    },
    footer: {
      description: "Sistema operativo para flotas, finanzas y cumplimiento fiscal.",
      legal: "Legal",
      legalNotice: "Aviso legal",
      privacy: "Política de privacidad (RGPD)",
      contact: "Contacto",
      readyQuestion: "¿Listo para digitalizar tu flota?",
      salesCta: "Hablar con ventas",
      copyright: "Todos los derechos reservados.",
    },
    moats: {
      title: "Capacidades de blindaje operativo",
      subtitle:
        "Capacidades diseñadas para maximizar retorno: más control, menos fuga de margen y decisiones con base financiera.",
      capabilities: [
        {
          title: "Certificación VeriFactu",
          description: "Cadena de trazabilidad fiscal y cumplimiento preparado para inspecciones AEAT 2026.",
        },
        {
          title: "EBITDA en tiempo real",
          description: "Visión financiera instantánea por ruta, cliente y vehículo para decidir con margen real.",
        },
        {
          title: "Portal del chófer",
          description: "Operativa de campo centralizada para partes, estados y comunicación sin fricción.",
        },
        {
          title: "Cotizador inteligente",
          description: "Presupuestos más rápidos y consistentes según costes reales, históricos y reglas de negocio.",
        },
        {
          title: "Control de vencimientos",
          description: "Alertas unificadas de documentos, revisiones y obligaciones críticas de la flota.",
        },
        {
          title: "Liquidaciones automáticas",
          description: "Cálculo y cierre de liquidaciones con menos errores y ciclos administrativos más cortos.",
        },
      ],
    },
    howItWorks: {
      title: "Cómo funciona",
      subtitle: "Onboarding pensado para operadores, no para consultores.",
      stepLabel: "Paso",
      steps: [
        {
          title: "Añade tu flota y costes fijos",
          desc: "Configura vehículos y estructura de costes en poco más de un minuto.",
          time: "~1 min",
        },
        {
          title: "Registra un porte",
          desc: "Desde la cabina o la oficina: origen, destino y precio en segundos.",
          time: "~30 seg",
        },
        {
          title: "El sistema hace el resto",
          desc: "Factura, calcula margen, VeriFactu y CO₂ automáticamente.",
          time: "Automático",
        },
      ],
    },
    roi: {
      title: "Simulador de ROI interactivo",
      subtitle: "Ajusta tu flota y el kilometraje medio. Los resultados se actualizan al instante.",
      fleetSize: "Tamaño de tu flota",
      trucksSuffix: "camiones",
      fleetRangeHint: "Entre 1 y 50 camiones",
      kmPerTruck: "Kilómetros medios por camión / mes",
      kmRangeHint: "500 – 12.000 km",
      adminSaved: "Administración ahorrada",
      adminSavedHint: "Estimación: 4 h por camión en tareas administrativas",
      economicSaving: "Ahorro económico estimado",
      economicSavingHint: "Valor hora referencia: 25 €",
      trackedEsg: "Huella ESG rastreada",
      trackedEsgHint: "Modelo km × 0,085 kg CO₂ (indicativo)",
      hoursPerMonth: "h/mes",
      kgPerMonth: "kg CO₂ / mes",
      monthSuffix: "/mes",
      summaryPrefix: "Recupera",
      summarySuffix: "al mes. Tu suscripción se paga sola.",
    },
    heroLegacy: {
      trustSignals: ["Soporte en España", "Onboarding en 24h", "Adaptado a VeriFactu 2026"],
      pill: "Plataforma B2B · Transporte y logística",
      titlePrefix: "El Sistema Operativo Definitivo para",
      titleHighlight: "Flotas Inteligentes",
      description:
        "Optimización del margen operativo (EBITDA), cumplimiento VeriFactu 2026 y trazabilidad financiera en un único sistema de control para dirección.",
      primaryCta: "Auditar mi flota",
      secondaryCta: "Ver demo",
      complianceNote: "Preparado para la normativa AEAT 2026 (Ley Crea y Crece)",
    },
  },
  sidebar: {
    developerApi: "API y Webhooks",
    developerApiSub: "Claves y endpoints",
    logout: "Cerrar sesión",
    demoMode: "Modo Demo",
    roleLabels: {
      owner: "Propietario",
      admin: "Administrador",
      traffic_manager: "Traffic Manager",
      driver: "Conductor",
      cliente: "Cliente",
      developer: "Desarrollador",
    } as const,
  },
  login: {
    tagline: "Inicia sesión en tu empresa",
    username: "Usuario",
    email: "Email",
    password: "Contraseña",
    submit: "Iniciar sesión",
    submitShort: "Entrar",
    pending: "Entrando…",
    pendingShort: "Entrando...",
    oauthDivider: "o continúa con",
    google: "Google",
    googlePending: "Conectando...",
    backToMarketing: "Volver al sitio público",
    oauthFail: "No se pudo iniciar sesión con Google.",
    supabasePending: "Configuración pendiente de Supabase.",
  },
  quota: {
    noData: "Sin datos de cuota",
    quotaPrefix: "Cuota:",
    fleetQuota: "Cuota flota",
    starterMsg:
      "Estás usando {used} de 5 vehículos. Pásate a PRO para gestionar hasta 25.",
    proMsg:
      "Módulo ESG bloqueado. Sube a ENTERPRISE para certificar tu huella de carbono.",
    enterpriseMsg: "Plan Enterprise · {used} vehículo(s) registrados (sin límite).",
    upgrade: "Mejorar plan",
    manageSubscription: "Gestionar suscripción",
    manageSubscriptionBusy: "Abriendo portal…",
    helpQuotaBilling: "Ayuda: planes y facturación (Stripe)",
  },
  common: {
    loadingEllipsis: "Cargando…",
    configPendingTitle: "Configuración pendiente",
    configPendingBody:
      "El sistema está en mantenimiento temporal. Falta completar la configuración de Supabase.",
  },
  portalCliente: {
    badge: "Portal cargador",
    mobileHeader: "Portal cliente",
    themeLight: "Modo claro",
    themeDark: "Modo oscuro",
    signOut: "Salir",
    navShipments: "Mis Portes",
    navInvoices: "Facturas",
    navEsg: "Sostenibilidad ESG",
    navBi: "BI en vivo",
    footer: {
      help: "Centro de ayuda",
      privacy: "Privacidad (RGPD)",
      legal: "Aviso legal",
      support: "Contacto / soporte",
      apiDebugPrefix: "API · ",
      productNote: "VeriFactu, ESG y cobro conforme a tu acuerdo comercial.",
    },
  },
  helpHub: {
    hubTitle: "Centro de ayuda",
    hubSubtitle:
      "Documentación comercial, facturación Stripe, seguridad, cumplimiento y operación. Busca por palabra clave o filtra por categoría.",
    searchPlaceholder: "Buscar en títulos y resúmenes…",
    searchLabel: "Buscar artículos",
    allCategories: "Todas",
    noResults: "No hay artículos que coincidan con tu búsqueda.",
    readArticle: "Leer artículo",
    footerLegal:
      "Los textos legales contractuales (SLA, privacidad) se entregan según tu acuerdo comercial. Para postura técnica de cumplimiento consulta la API pública de compliance.",
    footerPricing: "Ver planes",
    footerLogin: "Acceder al ERP",
    updatedLabel: "Actualizado",
    categories: {
      onboarding: "Primeros pasos",
      billing: "Facturación & Stripe",
      security: "Seguridad & datos",
      compliance: "Cumplimiento & AEAT",
      integrations: "Integraciones",
      support: "Soporte & SLA",
    },
  },
} as const;
