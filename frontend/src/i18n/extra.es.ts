/** Login, sidebar secundario, cuota, portal cliente, ayuda hub, comunes — ES */
export const extraEs = {
  landing: {
    brandAlt: "Logo de AB Logistics",
    nav: {
      simulator: "Simulador",
      advantage: "Ventaja",
      howItWorks: "Cómo funciona",
      platform: "Producto",
      trust: "Cumplimiento",
      pricing: "Precios",
      help: "Centro de ayuda",
      menuAria: "Menú",
      login: "Iniciar sesión",
      requestAccess: "Solicitar acceso al sistema",
      homeAria: "AB Logistics OS - inicio",
    },
    hero: {
      eyebrow: "Transporte · Finanzas · AEAT 2026",
      title: "Una sola plataforma para portes rentables y facturación a prueba de inspección.",
      description:
        "Desde el presupuesto hasta el cobro: flota, VeriFactu, conciliación y visibilidad de margen para dirección y tráfico. Misma oferta comercial en web y en Stripe: Compliance, Operational e Institutional.",
      primaryCta: "Crear cuenta y empezar",
      secondaryCta: "Ver planes y precios",
    },
    bento: {
      eyebrow: "Resultados",
      title: "Una plataforma, cuatro palancas de crecimiento",
      subtitle:
        "Diseñada para equipos que exigen trazabilidad fiscal, sostenibilidad medible y tesorería sin fricción.",
      cards: [
        {
          title: "Cumplimiento sin sustos",
          body: "Factura con tranquilidad y reduce riesgo en inspecciones, sin depender de procesos manuales.",
        },
        {
          title: "Rentabilidad + ESG en una vista",
          body: "Detecta rutas con fuga de margen y mejora tu huella con decisiones operativas accionables.",
        },
        {
          title: "Caja al día",
          body: "Automatiza cobros y conciliación para ganar visibilidad real de tesorería semana a semana.",
        },
        {
          title: "Decisiones más rápidas",
          body: "Prioriza acciones con recomendaciones guiadas para operaciones, finanzas y crecimiento comercial.",
        },
      ],
    },
    pricing: {
      features: [
        "Certificación VeriFactu",
        "Motor financiero / EBITDA avanzado",
        "Portal del chófer",
        "Cotizador inteligente",
        "Control de vencimientos",
        "Liquidaciones automáticas",
      ],
      title: "Planes publicados = planes de Stripe",
      subtitle:
        "Planes diseñados para recuperar margen y reducir horas administrativas desde el primer mes. Elige el nivel que encaja con tu volumen y evoluciona sin fricción conforme crece tu operativa.",
      recommended: "Recomendado",
      connecting: "Conectando...",
      requestAccess: "Siguiente: registro y checkout",
      subscribeCta: "Contratar con Stripe",
      ctaLoginToSubscribe: "Iniciar sesión y contratar",
      contactSalesCta: "Hablar con ventas",
      limitsFinite: "Hasta {{v}} vehículos · hasta {{u}} usuarios de panel",
      limitsUnlimited: "Flota y usuarios de panel ilimitados (Institutional)",
      pricingHelpBillingLink: "Centro de ayuda — Facturación y Stripe",
      vatExcluded: "IVA no incluido",
      missingStripeConfig:
        "La contratación online no está disponible temporalmente en este entorno. Te ayudamos a activarla o te enviamos enlace directo.",
      pricingStripeFallbackTitle: "Contratación en línea en preparación",
      pricingStripeFallbackBody:
        "En este entorno los enlaces de pago no están activos todavía. Puedes revisar el catálogo y los límites por plan; nuestro equipo comercial puede activar el checkout o enviarte un enlace de suscripción.",
      stripeGatewayError: "Hubo un problema al conectar con la pasarela segura.",
      stripeConnectionError: "No se pudo conectar con la pasarela segura. Inténtalo de nuevo.",
      pendingUserId: "USUARIO_PENDIENTE_DE_REGISTRO",
      monthSuffix: "/mes",
    },
    pricingPage: {
      title: "Contratar Compliance, Operational o Institutional",
      subtitle:
        "Elige plan y activa tu suscripción en pocos pasos. Si aún no tienes cuenta, regístrate y vuelve para continuar el alta.",
      empresaRequiredHint:
        "Sin empresa_id en la URL no se puede asociar el cobro. Tras registrarte, abre el enlace del correo de bienvenida o inicia sesión y ve a Suscripción.",
      stripeEnvHint:
        "Si necesitas ayuda para activar la contratación online, nuestro equipo te acompaña en el proceso.",
      envVarsList:
        "¿Prefieres asistencia? Te guiamos para dejar la suscripción operativa en una llamada corta.",
      funnelHint:
        "Flujo self-serve: registro → empresa creada → checkout Stripe desde esta página (con ?empresa_id=) o desde el menú Suscripción.",
      loginCta: "Iniciar sesión para pagar",
      backHome: "Volver a la web pública",
      headerLogin: "Acceso clientes",
    },
    socialProof: {
      eyebrow: "Por qué equipos de tráfico lo miran dos veces",
      title: "Menos cierre manual. Más control antes de que el margen se escape.",
      subtitle:
        "Pensado para empresas de transporte que ya facturan en serie y no pueden permitirse duplicar datos entre Excel, el ERP y el correo del gestor.",
      stats: [
        { value: "VeriFactu", label: "Registro fiscal con foco en trazabilidad e integridad" },
        { value: "ROI", label: "Impacto medible en margen, tiempo de cierre y control de caja" },
        { value: "Stripe", label: "Misma jerarquía Compliance / Operational / Institutional en checkout y producto" },
      ],
    },
    trustStrip: {
      eyebrow: "Cumplimiento y seguridad",
      title: "Cumplimiento y control para crecer con confianza",
      subtitle:
        "Combina operación, finanzas y cumplimiento en un único flujo para reducir errores, acelerar cierres y dar visibilidad a dirección.",
      bullets: [
        {
          title: "Trazabilidad fiscal",
          body: "Flujo de facturación preparado para normativa vigente, con trazabilidad clara para auditoría y gestoría.",
        },
        {
          title: "Seguridad por capas",
          body: "Seguridad por capas y separación de datos por empresa para operar con tranquilidad a medida que escalas.",
        },
        {
          title: "Cobro transparente",
          body: "Stripe Billing con Compliance, Operational e Institutional — mismos precios de catálogo en toda la superficie del producto.",
        },
      ],
    },
    techSpecs: {
      items: ["Cumplimiento VeriFactu", "Cobros y suscripción integrados", "Conciliación y tesorería", "Escalado para flotas en crecimiento"],
    },
    faq: {
      title: "Preguntas clave antes de implantar AB Logistics OS",
      subtitle:
        "Objeciones típicas de transporte, tráfico y dirección financiera — sin humo comercial.",
      items: [
        {
          q: "¿Es difícil migrar el histórico y los datos de mi flota actual?",
          a: "En absoluto. Puedes importar tu base de datos de clientes y vehículos de forma masiva, o empezar desde cero operando solo los portes nuevos. Nuestro equipo de onboarding B2B puede guiarte durante el primer mes para asegurar una transición sin fricción.",
        },
        {
          q: "¿Es rentable el sistema si mi flota tiene menos de 5 camiones?",
          a: "Totalmente. El volumen no exime de las obligaciones fiscales. El plan Compliance está diseñado para blindar a pequeñas flotas ante VeriFactu, eliminando horas de papeleo administrativo para que te centres en conducir tu negocio, no tu contabilidad.",
        },
        {
          q: "¿Cómo garantiza exactamente el software el cumplimiento de la ley VeriFactu?",
          a: "Te ayudamos a cumplir VeriFactu con un flujo guiado de facturación, trazabilidad de registros y evidencias listas para auditoría, reduciendo el trabajo manual del equipo.",
        },
        {
          q: "¿Están seguros mis datos financieros y los de mis clientes?",
          a: "Sí. Aplicamos seguridad por capas y aislamiento de datos por empresa para que tu información financiera y operativa esté protegida en todo momento.",
        },
        {
          q: "¿El sistema se integra con mis bancos para la conciliación y los cobros?",
          a: "Sí. AB Logistics OS está diseñado para integrarse con pasarelas institucionales como GoCardless y Stripe, automatizando los adeudos directos SEPA y la conciliación de facturas para que tu flujo de caja esté siempre actualizado.",
        },
        {
          q: "¿Cómo automatizan los reportes de emisiones de huella de carbono (ESG)?",
          a: "Nuestro motor cruza los datos de tus rutas con las certificaciones de tu flota (ej. Euro VI). Esto genera informes de emisiones precisos y listos para auditar, un requisito que las grandes multinacionales exigen cada vez más a sus proveedores logísticos.",
        },
        {
          q: "Si mi empresa crece rápidamente, ¿el software podrá soportarlo?",
          a: "Sí. Puedes empezar con una operativa pequeña y crecer sin migraciones traumáticas: el producto está pensado para escalar contigo en volumen y complejidad.",
        },
        {
          q: "¿Qué nivel de soporte técnico incluye la suscripción?",
          a: "Ofrecemos un soporte especializado. No hablamos con bots; tu equipo tendrá línea directa con soporte técnico para resolver dudas operativas, de integración o consultas sobre la lógica fiscal del sistema.",
        },
        {
          q: "¿Existen contratos de permanencia o costes de implantación ocultos?",
          a: "La transparencia es nuestro pilar. No cobramos \"setup fees\" ni exigimos contratos de permanencia a largo plazo. Es un modelo SaaS puro: pagas tu suscripción mensual (o anual bonificada) y puedes cancelar cuando lo decidas.",
        },
        {
          q: "¿Puedo probar la plataforma antes de comprometer la operativa de mi empresa?",
          a: "Entendemos que cambiar de ERP es una decisión crítica. Ofrecemos sesiones de demostración personalizadas y la posibilidad de ejecutar un piloto controlado para que tu director financiero valide la herramienta antes del despliegue total.",
        },
        {
          q: "¿Mis conductores van a rechazar otra app más?",
          a: "El portal del conductor está pensado para flujos cortos (estado del porte, entrega, documentación). Puedes implantar primero despacho y facturación, e ir extendiendo a campo cuando veáis valor. No sustituye el tacógrafo ni la normativa de tiempos de conducción: complementa la parte documental y comercial del porte.",
        },
        {
          q: "¿Qué pasa con el CMR, albaranes y la prueba en caso de siniestro o disputa con el cliente?",
          a: "Centralizamos la trazabilidad del expediente (origen, destino, precio, documentos asociados) para que despacho y administración trabajen sobre la misma verdad. La responsabilidad civil y mercantil sigue siendo de la mercancía y del contrato de transporte; el software reduce errores de transcripción y lagunas de documentación.",
        },
        {
          q: "Trabajamos con subcontratistas y agencias: ¿el sistema sirve para flotas mixtas?",
          a: "Sí. Puedes trabajar con estructura mixta (propia y subcontratada), mantener visibilidad por cliente/ruta y ampliar capacidades conforme aumente la complejidad operativa.",
        },
        {
          q: "¿Qué ocurre si AEAT cambia requisitos técnicos después de contratar?",
          a: "El producto se actualiza como SaaS: cuando la normativa o los esquemas oficiales evolucionen, desplegamos cambios en la nube sin que tengas que reinstalar servidores. Mantén comunicación con tu asesor fiscal: el software implementa la lógica acordada con la legislación vigente en cada release.",
        },
        {
          q: "¿Tengo que pagar antes de saber si encaja con mi TMS o mi gestoría?",
          a: "Puedes registrarte, crear la empresa y explorar el panel con el plan asignado; el checkout Stripe se alinea cuando decidas suscribirte (desde Suscripción o con enlace que incluya empresa_id). Si necesitas integraciones específicas, Operational e Institutional son los niveles habituales para volumen y certificación.",
        },
      ],
    },
    footer: {
      description: "Sistema operativo para flotas, finanzas y cumplimiento fiscal.",
      legal: "Legal",
      legalNotice: "Aviso legal",
      privacy: "Política de privacidad (RGPD)",
      cookies: "Política de cookies",
      terms: "Términos y condiciones",
      contact: "Contacto",
      readyQuestion: "¿Ya tienes cuenta o quieres ver el panel?",
      salesCta: "Iniciar sesión",
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
    forgotPassword: "¿Has olvidado tu contraseña?",
    forgotPasswordTitle: "Recuperar acceso",
    forgotPasswordSubtitle:
      "Indica el correo de tu cuenta. Si existe una cuenta asociada, recibirás un enlace para restablecer la contraseña.",
    sendInstructions: "Enviar instrucciones",
    checkEmailInbox:
      "Si el correo existe en nuestro sistema, recibirás un enlace de recuperación pronto.",
    emailSentTitle: "Correo enviado",
    forgotPasswordBackToLogin: "Volver al inicio de sesión",
    forgotPasswordEmailRequired: "Indica un correo electrónico válido.",
    forgotPasswordGenericError: "No se pudo completar la solicitud. Inténtalo de nuevo más tarde.",
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
      "Flota: {used}/5 vehículos. Facturas emitidas este mes: {inv_used}/{inv_limit}. Mejora a Operational (hasta 30 vehículos y sin tope de facturas).",
    proMsg:
      "Módulo ESG bloqueado. Sube a Institutional para certificar tu huella de carbono.",
    enterpriseMsg: "Plan Institutional · {used} vehículo(s) registrados (sin límite).",
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
    themeSystem: "Según el sistema",
    themeAppearance: "Apariencia",
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
