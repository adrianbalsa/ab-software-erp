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
        "Desde el presupuesto hasta el cobro: flota, VeriFactu, conciliación y visibilidad de margen para dirección y tráfico. Misma oferta comercial en web y en Stripe: Essential, Pro y Enterprise.",
      primaryCta: "Crear cuenta y empezar",
      secondaryCta: "Ver planes y precios",
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
        "Motor financiero / EBITDA avanzado",
        "Portal del chófer",
        "Cotizador inteligente",
        "Control de vencimientos",
        "Liquidaciones automáticas",
      ],
      title: "Planes publicados = planes de Stripe",
      subtitle:
        "Tres niveles con los mismos nombres en producto y en facturación: Essential (350 €), Pro (800 €) y Enterprise (1000 €) al mes + IVA. Add-ons opcionales (OCR Pack, Webhooks B2B Premium, LogisAdvisor IA Pro) se contratan desde el panel.",
      recommended: "Recomendado",
      connecting: "Conectando...",
      requestAccess: "Siguiente: registro y checkout",
      subscribeCta: "Contratar con Stripe",
      vatExcluded: "IVA no incluido",
      missingStripeConfig:
        "Falta configurar los Price IDs de Stripe en el frontend (NEXT_PUBLIC_STRIPE_PRICE_*). Consulta docs/operations/STRIPE_BILLING.md.",
      pricingStripeFallbackTitle: "Contratación en línea no disponible",
      pricingStripeFallbackBody:
        "Los enlaces de pago no están configurados en este entorno. Puedes revisar los planes; para contratar, contacta con ventas o completa la configuración de Stripe.",
      stripeGatewayError: "Hubo un problema al conectar con la pasarela segura.",
      stripeConnectionError: "No se pudo conectar con la pasarela segura. Inténtalo de nuevo.",
      pendingUserId: "USUARIO_PENDIENTE_DE_REGISTRO",
      monthSuffix: "/mes",
    },
    pricingPage: {
      title: "Contratar Essential, Pro o Enterprise",
      subtitle:
        "Precios de catálogo alineados con el backend y Stripe Billing. Si aún no tienes empresa_id, crea la cuenta, completa el onboarding y vuelve aquí o usa «Suscripción» en el panel.",
      empresaRequiredHint:
        "Sin empresa_id en la URL no se puede asociar el cobro. Tras registrarte, abre el enlace del correo de bienvenida o inicia sesión y ve a Suscripción.",
      stripeEnvHint:
        "En el build deben existir los tres NEXT_PUBLIC_STRIPE_PRICE_* (Essential vía BASIC o STARTER, PRO, ENTERPRISE).",
      envVarsList:
        "Ejemplo: NEXT_PUBLIC_STRIPE_PRICE_BASIC o NEXT_PUBLIC_STRIPE_PRICE_STARTER, NEXT_PUBLIC_STRIPE_PRICE_PRO, NEXT_PUBLIC_STRIPE_PRICE_ENTERPRISE.",
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
        { value: "RLS", label: "Cada tenant aislado a nivel de base de datos" },
        { value: "Stripe", label: "Misma jerarquía de planes en checkout y en documentación interna" },
      ],
    },
    trustStrip: {
      eyebrow: "Cumplimiento y seguridad",
      title: "VeriFactu: cadena de hashes y disciplina operativa",
      subtitle:
        "La prioridad del producto es la integridad del registro fiscal y la coherencia entre operación y facturación. Sin atajos que comprometan una inspección.",
      bullets: [
        {
          title: "Trazabilidad fiscal",
          body: "Diseñado para encadenamiento de registros y requisitos de facturación electrónica; QR y remisión cuando aplique normativa.",
        },
        {
          title: "Seguridad por capas",
          body: "TLS en tránsito, RLS en PostgreSQL por empresa y gestión de secretos alineada con buenas prácticas (sin credenciales en código).",
        },
        {
          title: "Cobro transparente",
          body: "Stripe Billing con planes Essential, Pro y Enterprise — mismos nombres y precios orientativos en toda la superficie del producto.",
        },
      ],
    },
    techSpecs: {
      items: ["VeriFactu-ready", "TLS + RLS PostgreSQL", "Stripe Billing", "GoCardless / SEPA"],
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
          a: "Totalmente. El volumen no exime de las obligaciones fiscales. Nuestro plan Essential está diseñado para blindar a pequeñas flotas ante VeriFactu, eliminando horas de papeleo administrativo para que te centres en conducir tu negocio, no tu contabilidad.",
        },
        {
          q: "¿Cómo garantiza exactamente el software el cumplimiento de la ley VeriFactu?",
          a: "Operamos como un \"búnker fiscal\". El motor de AB Logistics OS genera automáticamente el encadenamiento de facturas (hashes), emite el código QR reglamentario, garantiza la inmutabilidad de los registros y está preparado para la remisión automática a la AEAT.",
        },
        {
          q: "¿Están seguros mis datos financieros y los de mis clientes?",
          a: "La seguridad es de nivel bancario. Utilizamos encriptación AES-128 para datos sensibles y Row Level Security (RLS) estricto en PostgreSQL. Esto significa que a nivel de base de datos es físicamente imposible que un cliente acceda a la información de otro.",
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
          a: "AB Logistics OS nace en la nube con una arquitectura serverless capaz de escalar dinámicamente. Ya sea que gestiones 10 portes al mes o 10.000, el rendimiento del sistema (Plan Enterprise) se mantiene intacto sin tiempos de latencia.",
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
          a: "Sí. La arquitectura multi-tenant y los roles están pensados para que cada empresa vea solo su mundo (RLS). Puedes modelar clientes, rutas recurrentes y operativa interna; para modelos complejos de subcontratación en cadena, Pro y Enterprise amplían capacidades de análisis y certificación.",
        },
        {
          q: "¿Qué ocurre si AEAT cambia requisitos técnicos después de contratar?",
          a: "El producto se actualiza como SaaS: cuando la normativa o los esquemas oficiales evolucionen, desplegamos cambios en la nube sin que tengas que reinstalar servidores. Mantén comunicación con tu asesor fiscal: el software implementa la lógica acordada con la legislación vigente en cada release.",
        },
        {
          q: "¿Tengo que pagar antes de saber si encaja con mi TMS o mi gestoría?",
          a: "Puedes registrarte, crear la empresa y explorar el panel con el plan asignado; el checkout Stripe se alinea cuando decidas suscribirte (desde Suscripción o con enlace que incluya empresa_id). Si necesitas integraciones específicas, Pro y Enterprise son los niveles habituales para volumen y certificación.",
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
