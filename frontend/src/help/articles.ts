export type HelpCategory =
  | "onboarding"
  | "billing"
  | "security"
  | "compliance"
  | "integrations"
  | "support";

export type AppLocaleHelp = "es" | "en";

export type HelpArticle = {
  slug: string;
  category: HelpCategory;
  updated: string;
  titles: { es: string; en: string };
  excerpts: { es: string; en: string };
  body: { es: string; en: string };
};

/** Texto plano para búsqueda en el hub (título, resumen, slug y cuerpo). */
export function helpArticleSearchText(a: HelpArticle, locale: AppLocaleHelp): string {
  const body = (locale === "en" ? a.body.en : a.body.es)
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`[^`]+`/g, " ")
    .replace(/[#*_()[\]|-]/g, " ")
    .toLowerCase();
  const title = (locale === "en" ? a.titles.en : a.titles.es).toLowerCase();
  const excerpt = (locale === "en" ? a.excerpts.en : a.excerpts.es).toLowerCase();
  return `${title} ${excerpt} ${a.slug} ${body}`;
}

export const HELP_ARTICLES: HelpArticle[] = [
  {
    slug: "getting-started",
    category: "onboarding",
    updated: "2026-04-19",
    titles: { es: "Primeros pasos en AB Logistics OS", en: "Getting started with AB Logistics OS" },
    excerpts: {
      es: "Roles, navegación principal y qué esperar del panel operativo y financiero.",
      en: "Roles, main navigation, and what to expect from operations and finance.",
    },
    body: {
      es: `
### Cuenta y roles
Tu **rol** (propietario, administrador, traffic manager, conductor, cliente, desarrollador) define qué módulos ves en el menú lateral. Los módulos fiscales y de tesorería suelen estar reservados a administración.

### Primer día recomendado
1. Si eres **administrador** configurando la empresa (datos fiscales, flota, invitaciones), revisa la guía **[Onboarding de empresa](/help/company-onboarding)** (trayectoria de producto, fuera del checklist técnico de fase 8).
2. Sube una **factura** o crea un **porte** para activar KPIs en el dashboard.
3. Revisa **Sostenibilidad** si tu plan incluye ESG comercial.

### Idioma
Puedes alternar **ES / EN** desde el selector de idioma (barra lateral o cabeceras públicas). La preferencia se guarda en el navegador.
      `.trim(),
      en: `
### Account & roles
Your **role** (owner, admin, traffic manager, driver, customer, developer) controls which modules appear in the sidebar. Tax and treasury modules are usually restricted to administrators.

### Recommended first day
1. If you are an **admin** setting up the company (tax data, fleet, invitations), read **[Company onboarding](/help/company-onboarding)** (product journey; separate from phase 8 technical closure).
2. Upload an **invoice** or create a **shipment** to activate dashboard KPIs.
3. Review **Sustainability** if your plan includes commercial ESG.

### Language
Switch **ES / EN** from the language selector (sidebar or public headers). Preference is stored in the browser.
      `.trim(),
    },
  },
  {
    slug: "billing",
    category: "billing",
    updated: "2026-04-20",
    titles: { es: "Facturación SaaS con Stripe", en: "SaaS billing with Stripe" },
    excerpts: {
      es: "Checkout, Customer Portal, webhooks e idempotencia operativa.",
      en: "Checkout, Customer Portal, webhooks and operational idempotency.",
    },
    body: {
      es: `
### Modelo
Los planes **Compliance**, **Finance** y **Full-Stack** (slugs técnicos \`starter\`, \`pro\`, \`enterprise\`) se cobran como **suscripción** mediante **Stripe Billing**. Precios de catálogo orientativos: **39 €**, **149 €** y **449 €** / mes (+ IVA); el cargo efectivo depende de tu configuración fiscal y de Stripe Tax si lo activáis.

### Add-ons (referencia)
| Add-on | Orientativo |
|--------|-------------|
| OCR Pack | 15 € / mes |
| Webhooks B2B Premium | 49 € / mes |
| LogisAdvisor IA Pro | 29 € / mes |

Los \`price_*\` en Stripe deben coincidir con las variables \`STRIPE_PRICE_*\` documentadas en \`docs/operations/STRIPE_BILLING.md\`.

### Checkout
Un usuario **administrador** inicia el checkout desde **Suscripción** o desde la tarjeta de **cuota de flota**. Tras pagar, Stripe notifica al backend (\`checkout.session.completed\`) y se actualizan \`plan\`, límites de flota e IDs de cliente/suscripción.

### Customer Portal
Desde **Suscripción → Abrir portal de facturación** accedes al **Stripe Customer Portal** (tarjeta, facturas PDF, cancelación de renovación). Requiere haber completado al menos un checkout para existir \`stripe_customer_id\`.

### Webhooks obligatorios (operación)
Configura en Stripe Dashboard el endpoint **HTTPS** hacia \`/api/v1/webhooks/stripe\` con el **signing secret** almacenado como \`STRIPE_WEBHOOK_SECRET\`. Eventos mínimos recomendados:
- \`checkout.session.completed\`
- \`customer.subscription.updated\`
- \`customer.subscription.deleted\`
- \`invoice.paid\`

Las reentregas del mismo \`evt_*\` se tratan de forma **idempotente** (no duplican efectos en base de datos).

### Runbook
Ver documentación interna \`docs/operations/STRIPE_BILLING.md\` para checklist de despliegue y variables \`STRIPE_* / PUBLIC_APP_URL\`.
      `.trim(),
      en: `
### Model
**Compliance**, **Finance** and **Full-Stack** (technical slugs \`starter\`, \`pro\`, \`enterprise\`) are charged as **subscriptions** via **Stripe Billing**. Indicative list prices: **€39**, **€149** and **€449** / month (+ VAT); actual charges depend on your tax setup and Stripe Tax if enabled.

### Add-ons (reference)
| Add-on | Indicative |
|--------|------------|
| OCR Pack | €15 / month |
| Webhooks B2B Premium | €49 / month |
| LogisAdvisor IA Pro | €29 / month |

Stripe \`price_*\` IDs should match \`STRIPE_PRICE_*\` env vars documented in \`docs/operations/STRIPE_BILLING.md\`.

### Checkout
An **admin** user starts checkout from **Subscription** or the **fleet quota** card. After payment, Stripe notifies the backend (\`checkout.session.completed\`) and \`plan\`, fleet limits and customer/subscription IDs are updated.

### Customer portal
From **Subscription → Open billing portal** you reach the **Stripe Customer Portal** (card, PDF invoices, cancel renewal). At least one checkout must exist so \`stripe_customer_id\` is present.

### Required webhooks (operations)
Configure the **HTTPS** endpoint in Stripe Dashboard to \`/api/v1/webhooks/stripe\` with the **signing secret** stored as \`STRIPE_WEBHOOK_SECRET\`. Minimum recommended events:
- \`checkout.session.completed\`
- \`customer.subscription.updated\`
- \`customer.subscription.deleted\`
- \`invoice.paid\`

Duplicate deliveries of the same \`evt_*\` are handled **idempotently**.

### Runbook
See \`docs/operations/STRIPE_BILLING.md\` for deployment checklist and \`STRIPE_* / PUBLIC_APP_URL\` variables.
      `.trim(),
    },
  },
  {
    slug: "audit-evidence-pack",
    category: "compliance",
    updated: "2026-04-20",
    titles: {
      es: "Paquete de evidencias para auditores (ZIP)",
      en: "Auditor evidence pack (ZIP download)",
    },
    excerpts: {
      es: "Descarga ZIP Due Diligence: compliance público, catálogo de precios y security.txt (sin PII operativo).",
      en: "DD-style ZIP: public compliance JSON, pricing catalog and security.txt (no operational PII).",
    },
    body: {
      es: `
### Qué es
Un **ZIP** generado por la API con evidencias de **postura de plataforma** y **matriz comercial de referencia**, pensado para Due Diligence y auditores externos. **No** incluye facturas, portes ni datos personales de tus clientes.

### Cómo descargarlo (rol *owner*)
1. Inicia sesión en el panel.
2. Abre **Finanzas → Auditoría fiscal** (\`/dashboard/finanzas/auditoria\`).
3. Usa **Descargar paquete auditor (ZIP)**.

El backend expone \`GET /api/v1/export/audit-package\` (JWT de propietario).

### Contenido típico del ZIP
- \`INDEX.md\` — índice y enlaces a documentación del repositorio.
- \`public_compliance_snapshot.json\` — misma información que \`GET /api/v1/public/compliance\` más metadatos de generación.
- \`pricing_catalog.json\` — planes Compliance / Finance / Full-Stack y add-ons (referencia \`app/core/plans.py\`).
- \`security.txt\` — copia del cuerpo RFC 9116.

### Límites
No sustituye al **Data Room** legal ni a exportaciones fiscales/ESG con su propio alcance normativo; complementa la narrativa de compliance y billing.
      `.trim(),
      en: `
### What it is
A **ZIP** built by the API with **platform posture** and **commercial catalog reference** evidence for Due Diligence and external auditors. It does **not** include invoices, shipments or your customers’ personal data.

### How to download (*owner* role)
1. Sign in to the dashboard.
2. Open **Finance → Tax audit** (\`/dashboard/finanzas/auditoria\`).
3. Click **Download auditor pack (ZIP)**.

The backend route is \`GET /api/v1/export/audit-package\` (owner JWT).

### Typical ZIP contents
- \`INDEX.md\` — index and pointers to repository documentation.
- \`public_compliance_snapshot.json\` — same payload as \`GET /api/v1/public/compliance\` plus generation metadata.
- \`pricing_catalog.json\` — Compliance / Finance / Full-Stack plans and add-ons (see \`app/core/plans.py\`).
- \`security.txt\` — RFC 9116 body snapshot.

### Limits
This does not replace a legal **Data Room** or tax/ESG exports with their own regulatory scope; it complements compliance and billing narrative.
      `.trim(),
    },
  },
  {
    slug: "esg-external-verification",
    category: "compliance",
    updated: "2026-04-20",
    titles: {
      es: "Verificación externa de certificados ESG",
      en: "External verification of ESG certificates",
    },
    excerpts: {
      es: "pending_external_audit → externally_verified; export ISO sin PII; webhook HMAC; rate limit público.",
      en: "pending_external_audit → externally_verified; ISO export without PII; HMAC webhook; public rate limit.",
    },
    body: {
      es: `
### Flujo
1. **Full-Stack (Enterprise):** al descargar un certificado PDF con la opción de **validación oficial**, el estado pasa a \`pending_external_audit\` y se genera un **código QR** hacia \`GET /v1/public/verify-esg/{code}\`.
2. La verificación pública devuelve huellas y agregados de emisiones **sin** exponer IDs de porte/factura en el JSON.
3. La certificadora (o operación interna) confirma: **webhook** \`POST /api/v1/webhooks/esg-external-verify\` con cuerpo JSON \`{"verification_code":"…"}\` y cabecera \`X-ABL-ESG-Signature\` (HMAC-SHA256 del body con \`ESG_EXTERNAL_WEBHOOK_SECRET\`), o el **propietario** cierra manualmente con \`POST /api/v1/esg/certificate/externally-verify/{code}\`.
4. Estado final: \`externally_verified\`.

### Export agregado sin PII (ISO 14083)
- \`GET /api/v1/esg/emissions-export-iso14083?fecha_inicio=&fecha_fin=&formato=csv|json\` (JWT owner / traffic_manager / gestor).
- Con \`formato=json\` y \`for_external_auditor=true\`, el bloque \`meta\` **no** incluye \`empresa_id\` (entrega a terceros).

### Registro de certificados
- \`GET /api/v1/esg/certificate-registry\` — lista reciente de códigos y estados (sin \`subject_id\`).

### Rate limit público
- \`GET /v1/public/verify-esg/…\` está limitado por **IP** (SlowAPI). Variable \`ESG_PUBLIC_VERIFY_RATELIMIT\` (por defecto \`60/minute\`); reiniciar workers al cambiar.

### UI
- **Sostenibilidad → Auditoría de huella** — sección *Verificación externa y export ISO* (registro, descargas, cierre por owner).
      `.trim(),
      en: `
### Flow
1. **Full-Stack (Enterprise):** when downloading a certificate PDF with **official validation**, status becomes \`pending_external_audit\` and a **QR** points to \`GET /v1/public/verify-esg/{code}\`.
2. The public response includes hashes and emission aggregates **without** shipment/invoice IDs in the JSON.
3. The auditor (or internal ops) confirms via **webhook** \`POST /api/v1/webhooks/esg-external-verify\` with JSON \`{"verification_code":"…"}\` and header \`X-ABL-ESG-Signature\` (HMAC-SHA256 of the raw body with \`ESG_EXTERNAL_WEBHOOK_SECRET\`), or the **owner** closes manually with \`POST /api/v1/esg/certificate/externally-verify/{code}\`.
4. Final state: \`externally_verified\`.

### Aggregated export without PII (ISO 14083)
- \`GET /api/v1/esg/emissions-export-iso14083?fecha_inicio=&fecha_fin=&formato=csv|json\` (JWT owner / traffic_manager / gestor).
- With \`formato=json\` and \`for_external_auditor=true\`, the \`meta\` block **omits** \`empresa_id\` for third-party handoff.

### Certificate registry
- \`GET /api/v1/esg/certificate-registry\` — recent codes and statuses (no \`subject_id\`).

### Public rate limit
- \`GET /v1/public/verify-esg/…\` is limited **per IP** (SlowAPI). Set \`ESG_PUBLIC_VERIFY_RATELIMIT\` (default \`60/minute\`); restart workers after changes.

### UI
- **Sustainability → Carbon footprint audit** — *External verification & ISO export* section (registry, downloads, owner close).
      `.trim(),
    },
  },
  {
    slug: "security-data",
    category: "security",
    updated: "2026-04-19",
    titles: { es: "Seguridad, cifrado y datos personales", en: "Security, encryption and personal data" },
    excerpts: {
      es: "RGPD, segregación por tenant, secretos y buenas prácticas operativas.",
      en: "GDPR, tenant isolation, secrets and operational best practices.",
    },
    body: {
      es: `
### Principios
- **Multi-tenant** con contexto de empresa en API y políticas de acceso.
- **Cifrado** de secretos sensibles y claves gestionadas vía proveedor de secretos cuando está configurado (Vault / AWS / env según despliegue).
- **Registros** de auditoría en rutas críticas (fiscal, banca, admin).

### RGPD
Tratamos datos personales conforme a la **Política de privacidad** contractual. Los exportes y portales limitan la información al **mínimo necesario** para la relación comercial o la operación logística.

### Contacto de seguridad
La divulgación coordinada y el buzón de contacto siguen el estándar **security.txt** cuando está publicado en el dominio de la aplicación. Para hallazgos, usa el canal indicado en tu contrato o el correo de seguridad corporativo.
      `.trim(),
      en: `
### Principles
- **Multi-tenant** with company context in APIs and access policies.
- **Encryption** of sensitive secrets and keys via a secret manager when configured (Vault / AWS / env depending on deployment).
- **Audit logs** on critical routes (tax, banking, admin).

### GDPR
We process personal data under your contractual **Privacy policy**. Exports and portals minimise data to what is **necessary** for the commercial or logistics relationship.

### Security contact
Coordinated disclosure follows **security.txt** when published on the app domain. For findings, use the channel defined in your contract or your corporate security mailbox.
      `.trim(),
    },
  },
  {
    slug: "verifactu-overview",
    category: "compliance",
    updated: "2026-04-19",
    titles: { es: "VeriFactu y trazabilidad fiscal", en: "VeriFactu and tax traceability" },
    excerpts: {
      es: "Huellas, cadena AEAT y buenas prácticas para no romper la integridad.",
      en: "Hashes, AEAT chain and practices to preserve integrity.",
    },
    body: {
      es: `
### Qué resuelve
**VeriFactu** asegura trazabilidad de facturas con **huellas** y encadenamiento conforme a la normativa aplicable en tu despliegue.

### Buenas prácticas
- No alteres facturas ya selladas sin usar los flujos soportados por el producto.
- Mantén **series** y datos de emisor coherentes con la configuración de empresa.
- Usa la **auditoría fiscal** del panel para revisar eventos inmutables.

### Limitación
El cumplimiento final depende de la **correcta configuración** de tu entorno (certificados, NIF, series) y de la operación contable de tu organización.
      `.trim(),
      en: `
### What it solves
**VeriFactu** provides invoice traceability with **hashes** and chaining according to the regulations applicable to your deployment.

### Good practices
- Do not alter sealed invoices outside the supported product flows.
- Keep **series** and issuer data aligned with company settings.
- Use the **tax audit** module to review immutable events.

### Limitation
Final compliance depends on **correct configuration** (certificates, tax IDs, series) and your organisation’s accounting operations.
      `.trim(),
    },
  },
  {
    slug: "banking-treasury",
    category: "integrations",
    updated: "2026-04-19",
    titles: { es: "Banca y tesorería (GoCardless)", en: "Banking & treasury (GoCardless)" },
    excerpts: {
      es: "Conexión de cuentas, sincronización y conciliación asistida.",
      en: "Account linking, sync and assisted reconciliation.",
    },
    body: {
      es: `
### Alcance
La **tesorería** permite conectar cuentas vía **GoCardless** (según plan y permisos) e importar movimientos para alimentar KPIs y **conciliación** con facturas.

### Operación
- Revisa la **última sincronización**; si supera 48 h, vuelve a importar.
- La **conciliación IA** propone coincidencias; la decisión final es humana o según políticas internas.

### Secretos
Las credenciales de integración deben residir en el **gestor de secretos** del entorno (no en código ni en repositorio).
      `.trim(),
      en: `
### Scope
**Treasury** lets you link accounts via **GoCardless** (depending on plan and permissions) and import transactions for KPIs and **reconciliation** with invoices.

### Operations
- Check **last sync**; if it is older than 48h, import again.
- **AI reconciliation** suggests matches; final decisions follow your internal policies.

### Secrets
Integration credentials must live in the environment **secret manager** (not in code or the repo).
      `.trim(),
    },
  },
  {
    slug: "api-b2b-webhooks",
    category: "integrations",
    updated: "2026-04-19",
    titles: { es: "API B2B y webhooks salientes", en: "B2B API and outbound webhooks" },
    excerpts: {
      es: "Claves, rotación y buenas prácticas para integradores.",
      en: "Keys, rotation and best practices for integrators.",
    },
    body: {
      es: `
### Acceso
Los administradores pueden generar claves y definir **webhooks salientes** desde **API y Webhooks** en el panel.

### Seguridad
- Rota claves periódicamente y tras baja de personal con acceso.
- Valida la **firma** o el secreto compartido según el contrato de integración.
- Limita IPs si tu gateway lo permite.

### Soporte a integradores
Para incidencias de conectividad o esquemas, abre ticket según tu **SLA** comercial.
      `.trim(),
      en: `
### Access
Admins can issue keys and configure **outbound webhooks** from **API & Webhooks** in the app.

### Security
- Rotate keys regularly and after staff offboarding.
- Validate **signatures** or shared secrets per your integration contract.
- Restrict IPs if your gateway supports it.

### Integrator support
Open a ticket per your commercial **SLA** for connectivity or schema issues.
      `.trim(),
    },
  },
  {
    slug: "portal-cliente",
    category: "support",
    updated: "2026-04-19",
    titles: {
      es: "Portal del cargador (autoservicio)",
      en: "Shipper portal (self-service)",
    },
    excerpts: {
      es: "Mis portes, facturas VeriFactu, ESG, domiciliación SEPA y aceptación de condiciones comerciales.",
      en: "Shipments, VeriFactu invoices, ESG, SEPA mandate and commercial terms acceptance.",
    },
    body: {
      es: `
### Acceso
Los usuarios con rol **cliente** entran en \`/portal-cliente\` (redirección desde \`/portal\`). Inicia sesión con el mismo flujo que el ERP; si tu administrador te ha invitado, completa **contraseña** y perfil según el email de bienvenida.

### Primera visita: condiciones comerciales
La primera vez puede aparecer un **informe de riesgo** y la aceptación del **cobro SEPA** como condición para operar. Debes marcar la casilla y **confirmar** para continuar.

### Qué puedes hacer
- **Mis portes**: activos (actualización periódica) e histórico con descarga de **POD** (albarán PDF) y **certificado GLEC / ISO 14083** por porte entregado.
- **Facturas**: PDF y, si existe registro sellado, **XML VeriFactu**. Puedes iniciar la **domiciliación GoCardless** para automatizar cobros (redirige al banco y vuelve a \`/portal-cliente/facturas?setup=success\`).
- **Sostenibilidad ESG**: resumen de ahorro de CO₂ acumulado (YTD) y **CSV** exportable, alineado al mismo motor que los certificados.

### Idioma y pie de página
Selector **ES / EN** en la cabecera. En el pie encontrarás enlaces a **Centro de ayuda**, **Privacidad (RGPD)**, **Aviso legal** y **contacto / soporte** (correo configurable por la plataforma).

### Pruebas automáticas (equipo técnico)
Smoke **Playwright** opt-in: variables \`E2E_PORTAL_CLIENTE_JWT\` y/o \`E2E_PORTAL_CLIENT_EMAIL\` + \`E2E_PORTAL_CLIENT_PASSWORD\`, y \`PLAYWRIGHT_TEST_BASE_URL\` o \`PLAYWRIGHT_BASE_URL\`. Ver \`frontend/tests/portal-cliente.spec.ts\`.
      `.trim(),
      en: `
### Access
Users with the **cliente** role use \`/portal-cliente\` (legacy \`/portal\` redirects). Sign in like the ERP; if an admin invited you, complete **password** and profile steps from the welcome email.

### First visit: commercial terms
On first access you may see a **risk summary** and acceptance of **SEPA Direct Debit** as a condition to operate. Check the box and **confirm** to continue.

### What you can do
- **My shipments**: active shipments (periodic refresh) and history with **POD** (delivery note PDF) and **GLEC / ISO 14083** certificate per completed shipment.
- **Invoices**: PDF and, when a sealed record exists, **VeriFactu XML**. You can start **GoCardless** mandate setup for automated collection (bank redirect, then return to \`/portal-cliente/facturas?setup=success\`).
- **ESG sustainability**: accumulated CO₂ savings (YTD) and downloadable **CSV**, same engine as certificates.

### Language & footer
**ES / EN** selector in the header. The footer links to the **help centre**, **privacy (GDPR)**, **legal notice** and **contact / support** (mailbox configurable by the platform).

### Automated tests (engineering)
Opt-in **Playwright** smoke: \`E2E_PORTAL_CLIENTE_JWT\` and/or \`E2E_PORTAL_CLIENT_EMAIL\` + \`E2E_PORTAL_CLIENT_PASSWORD\`, plus \`PLAYWRIGHT_TEST_BASE_URL\` or \`PLAYWRIGHT_BASE_URL\`. See \`frontend/tests/portal-cliente.spec.ts\`.
      `.trim(),
    },
  },
  {
    slug: "sla-support",
    category: "support",
    updated: "2026-04-19",
    titles: { es: "SLA, soporte y escalado", en: "SLA, support and escalation" },
    excerpts: {
      es: "Tiempos de respuesta, severidades y canales contractuales.",
      en: "Response times, severities and contractual channels.",
    },
    body: {
      es: `
### Niveles de severidad
Clasifica incidencias como **S1** (servicio detenido), **S2** (degradación relevante) o **S3** (consulta / mejora). Los tiempos de respuesta y workaround se definen en el **SLA** firmado.

### Canales
Usa el **buzón de soporte** y el **teléfono on-call** indicados en tu contrato. No pubiques credenciales en tickets.

### Evidencias
Para auditorías o due diligence, conserva **referencias de ticket**, capturas de estado del servicio y correlación con \`X-Request-ID\` cuando el equipo de plataforma lo solicite.
      `.trim(),
      en: `
### Severity levels
Classify issues as **S1** (service down), **S2** (material degradation) or **S3** (question / enhancement). Response and workaround times are defined in the signed **SLA**.

### Channels
Use the **support mailbox** and **on-call phone** from your contract. Never post credentials in tickets.

### Evidence
For audits or due diligence, keep **ticket references**, service status captures and correlation with \`X-Request-ID\` when the platform team requests it.
      `.trim(),
    },
  },
  {
    slug: "company-onboarding",
    category: "onboarding",
    updated: "2026-04-19",
    titles: {
      es: "Onboarding de empresa (trayectoria de producto)",
      en: "Company onboarding (product journey)",
    },
    excerpts: {
      es: "Qué suele incluir la puesta en marcha del tenant y cómo se separa del checklist de escala (fase 8).",
      en: "What tenant go-live usually covers and how it differs from the scale checklist (phase 8).",
    },
    body: {
      es: `
### Alcance
Este bloque describe la **experiencia de primera configuración** de una empresa en AB Logistics OS: datos maestros, usuarios, límites de flota, integraciones opcionales y formación interna. Es **trabajo de producto y operación**, no el mismo criterio que “Help Center + i18n frontend” cerrados en repositorio.

### Qué suele hacer un administrador
- Completar **datos fiscales** y series VeriFactu según el despliegue.
- Invitar a **usuarios** con roles adecuados (owner, admin, traffic manager, etc.).
- Revisar **cuota de flota** y plan SaaS (ver también [Facturación SaaS](/help/billing)).
- Conectar **banca** o **API B2B** si aplica al contrato.

### Relación con la fase 8 (repo)
La fase 8 en código se centra en **autoservicio documental** (centro de ayuda), **i18n en frontend** y **portal cliente** ya enlazados al help. El **onboarding guiado** (tours, checklists in-app, emails transaccionales) puede seguir en **backlog** o en una fase posterior sin bloquear el cierre de esos entregables.

### Más lectura
- [Primeros pasos](/help/getting-started)
- [VeriFactu y trazabilidad](/help/verifactu-overview)
      `.trim(),
      en: `
### Scope
This article describes the **first-time company setup** experience in AB Logistics OS: master data, users, fleet limits, optional integrations and internal training. It is **product and operations work**, not the same bar as “help centre + frontend i18n” closed in the repository.

### Typical admin tasks
- Complete **tax data** and VeriFactu series for your deployment.
- Invite **users** with the right roles (owner, admin, traffic manager, etc.).
- Review **fleet quota** and SaaS plan (see also [SaaS billing](/help/billing)).
- Connect **banking** or the **B2B API** if your contract includes them.

### Relation to phase 8 (repo)
Phase 8 in code focuses on **self-service documentation** (help centre), **frontend i18n** and the **customer portal** linked to help. **Guided onboarding** (tours, in-app checklists, transactional emails) can live in a **backlog** or a later phase without blocking closure of those deliverables.

### Further reading
- [Getting started](/help/getting-started)
- [VeriFactu and traceability](/help/verifactu-overview)
      `.trim(),
    },
  },
  {
    slug: "i18n-frontend",
    category: "support",
    updated: "2026-04-19",
    titles: {
      es: "Idioma e i18n (frontend)",
      en: "Language & frontend i18n",
    },
    excerpts: {
      es: "Selector ES/EN, catálogos de textos y alcance hasta escala internacional.",
      en: "ES/EN selector, message catalogues and scope until international scale.",
    },
    body: {
      es: `
### Cómo cambiar de idioma
El selector **ES / EN** está en la barra lateral del ERP, cabeceras públicas (login, precios, help) y en el **portal del cargador**. La preferencia se guarda en \`localStorage\` del navegador.

### Dónde viven los textos
- **Shell y navegación**: \`frontend/src/i18n/shell.*.ts\`, \`extra.*.ts\` (login, cuota, portal, hub de ayuda).
- **Páginas prioritarias**: \`frontend/src/i18n/pages.*.ts\` (dashboard, tesorería, facturas ERP, finanzas, portal: mis portes, ESG, facturas, riesgo comercial).
- **Fechas y números en portal**: \`frontend/src/lib/portalLocaleFormat.ts\` y \`localeFormat.ts\` (EUR).

### Alcance acordado (fase 8)
El i18n **solo en frontend** cubre la experiencia de usuario en Next.js hasta que se defina una expansión internacional mayor (emails backend, PDFs dinámicos, mensajes API, etc.). Eso queda fuera del cierre actual salvo nueva fase explícita.

### Ayuda relacionada
- [Primeros pasos](/help/getting-started)
- [Portal del cargador](/help/portal-cliente)
      `.trim(),
      en: `
### How to switch language
The **ES / EN** selector is in the ERP sidebar, public headers (login, pricing, help) and the **shipper portal**. Preference is stored in the browser \`localStorage\`.

### Where strings live
- **Shell & navigation**: \`frontend/src/i18n/shell.*.ts\`, \`extra.*.ts\` (login, quota, portal, help hub).
- **Priority pages**: \`frontend/src/i18n/pages.*.ts\` (dashboard, treasury, ERP invoices, finance, portal: shipments, ESG, invoices, commercial risk).
- **Portal dates & numbers**: \`frontend/src/lib/portalLocaleFormat.ts\` and \`localeFormat.ts\` (EUR).

### Agreed scope (phase 8)
**Frontend-only** i18n covers the Next.js UX until a broader international rollout is scoped (backend emails, dynamic PDFs, API messages, etc.). That remains out of the current closure unless a new phase says otherwise.

### Related help
- [Getting started](/help/getting-started)
- [Shipper portal](/help/portal-cliente)
      `.trim(),
    },
  },
  {
    slug: "erp-invoicing",
    category: "compliance",
    updated: "2026-04-19",
    titles: {
      es: "Facturación en el ERP (emitidas y rectificativas)",
      en: "ERP invoicing (issued invoices & corrections)",
    },
    excerpts: {
      es: "Listado de facturas, VeriFactu, PDF inmutable y rectificativas R1.",
      en: "Invoice list, VeriFactu, immutable PDF and R1 corrections.",
    },
    body: {
      es: `
### Listado de facturas
En **Facturas** del panel verás el número, tipo, fecha, total, estado AEAT y acciones (PDF, CSV AEAT, rectificación cuando aplique).

### VeriFactu e integridad
Las huellas y la cadena fiscal se describen en **[VeriFactu y trazabilidad](/help/verifactu-overview)**. No modifiques datos sellados fuera de los flujos soportados (p. ej. rectificativa **R1**).

### Rectificativas
Para facturas **F1** puedes abrir el flujo de **rectificación** con motivo; el sistema emite la corrección según las reglas configuradas.

### Portal cargador vs ERP
El **portal del cargador** muestra facturación emitida **a la cuenta del cliente** (autoservicio). La vista **ERP** es la de emisión y cumplimiento interno. Ver [Portal del cargador](/help/portal-cliente).
      `.trim(),
      en: `
### Invoice list
Under **Invoices** in the app you see number, type, date, total, AEAT status and actions (PDF, AEAT CSV, correction when applicable).

### VeriFactu & integrity
Hashes and the tax chain are covered in **[VeriFactu and traceability](/help/verifactu-overview)**. Do not alter sealed data outside supported flows (e.g. **R1** corrections).

### Corrections
For **F1** invoices you can start a **correction** flow with a reason; the system issues the correction according to configured rules.

### Shipper portal vs ERP
The **shipper portal** shows invoices issued **to the customer account** (self-service). The **ERP** view is for internal issuance and compliance. See [Shipper portal](/help/portal-cliente).
      `.trim(),
    },
  },
];

export function articleBySlug(slug: string): HelpArticle | undefined {
  return HELP_ARTICLES.find((a) => a.slug === slug);
}
