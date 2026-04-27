# Roadmap: integraciones y optimización de negocio

Orden sugerido por **impacto en ingresos / riesgo / esfuerzo**. Cada ítem indica quién lleva más peso: **Agente (IA + cambios en repo)** vs **Tú (decisiones, cuentas, proveedor, legal)**.

---

## Fase 0 — Base (1–3 días)

| # | Iniciativa | Orden | Más Agente | Más Tú |
|---|------------|-------|------------|--------|
| 0.1 | **Sentry operativo** (DSN, releases, muestreo razonable en prod) | Primero | Ajustes de código, checks CI, documentación en env. | Crear proyecto Sentry, DSN, política de retención y acceso al equipo. |
| 0.2 | **`ALERT_WEBHOOK_URL`** (Slack / Discord / PagerDuty) para errores críticos | Segundo | Cablear ya existente si falta handler, tests, doc en `production.env.example`. | Elegir canal, crear webhook, definir quién responde fuera de horario. |

**Por qué primero:** sin visibilidad y alerta, el resto del roadmap se ejecuta a ciegas.

---

## Fase 1 — Ingresos y confianza (1–2 semanas)

| # | Iniciativa | Orden | Más Agente | Más Tú |
|---|------------|-------|------------|--------|
| 1.1 | **Stripe**: webhooks, Customer Portal, flujos cancelación/reactivación | 1 | Tests e2e/contract, alinear `plans` con Prices, manejo de errores en UI. | Dashboard Stripe, productos/precios, impuestos, datos fiscales empresa, política de reembolsos. |
| 1.2 | **Resend**: dominio verificado, remitentes, plantillas (reset, bienvenida, ESG) | 2 | HTML/textos, variables, pruebas de envío desde staging. | Alta en Resend, DNS SPF/DKIM/DMARC, aprobación de copy legal/comercial. |
| 1.3 | **Email unificado**: cuándo SMTP vs Resend (facturas vs transaccional) | 3 | Refactor documentado, logs claros, fallbacks. | Decisión de negocio: “¿factura solo SMTP o también Resend?” |

**Por qué:** impacto directo en cobro y en percepción profesional del producto.

---

## Fase 2 — Operativa y margen (2–3 semanas, en paralelo parcial)

| # | Iniciativa | Orden | Más Agente | Más Tú |
|---|------------|-------|------------|--------|
| 2.1 | **GoCardless**: sandbox → prod, webhooks, pantallas de error amigables | 1 | Código, idempotencia, logs, checklist en docs. | Contrato GoCardless, credenciales prod, revisión con finanzas. |
| 2.2 | **Google Maps**: cuotas, caché, batching, métricas de coste | 2 | Instrumentación, límites por tenant, tests. | Presupuesto GCP/Maps, alertas de billing en consola Google. |
| 2.3 | **IA (Advisor)**: un proveedor primario + fallback + límites de coste | 3 | LiteLLM/routing, timeouts, rate limits, trazas. | Presupuesto tokens, proveedor preferido (OpenAI vs Anthropic vs Azure), política de datos (DPA). |

**Por qué:** reduce soporte (“no me cobró”, “el mapa falla”) y protege margen.

---

## Fase 3 — Cumplimiento y seguridad (continuo, hitos trimestrales)

| # | Iniciativa | Orden | Más Agente | Más Tú |
|---|------------|-------|------------|--------|
| 3.1 | **VeriFactu / AEAT**: entornos test/prod, certificados, runbooks | 1 | Cliente SOAP, validaciones XSD, tests regresión. | Certificados cualificados, ventana con asesor fiscal, alta en entornos AEAT. |
| 3.2 | **Secretos**: Vault o AWS Secrets Manager en prod | 2 | Integración `SECRET_MANAGER_*`, rotación documentada. | Cuenta AWS/Vault, IAM, auditoría, rotación acordada con ops. |
| 3.3 | **Backup / DR** (Supabase + Postgres) | 3 | Scripts, comprobaciones restore en CI opcional. | RPO/RTO acordados, contrato Supabase, prueba de restore manual trimestral. |

**Por qué:** riesgo regulatorio y reputacional; encaja después de que el dinero y la operativa respiren.

### Cierres ejecutados

| ID | Estado | Resultado | Evidencia |
|----|--------|-----------|-----------|
| **SEC-001** | ✅ Cerrado | Génesis Hash VeriFactu migrado a Secret Manager por emisor; sin semilla hardcodeada/compartida en runtime, `.env`, código o logs. | `SecretManagerService.get_verifactu_genesis_hash`, `verifactu_genesis.py`, emisión/finalización en `facturas_service.py`; tests enfocados `27 passed`. |

---

## Fase 4 — Crecimiento (cuando el núcleo esté estable)

| # | Iniciativa | Orden | Más Agente | Más Tú |
|---|------------|-------|------------|--------|
| 4.1 | **CRM** (HubSpot, Pipedrive, …) | Opcional | Webhooks desde app, Zapier/Make, o SDK mínimo. | Elección de CRM, pipeline comercial, formación equipo ventas. |
| 4.2 | **Product analytics** (PostHog, Amplitude, …) | Opcional | Eventos server/client, privacidad, consentimiento. | Qué embudo medir, dashboards, ownership datos. |
| 4.3 | **Soporte** (Intercom, Zendesk, …) | Opcional | Widget, SSO si aplica. | SLA con cliente, horario, macros. |

**Por qué:** maximiza conversión y retención cuando el producto ya es fiable.

---

## Resumen “quién hace más”

| Dominio | Más Agente | Más Tú |
|---------|------------|--------|
| Código, tests, docs en repo, CI | ●●● | ● |
| Cuentas proveedor, API keys, billing cloud | ● | ●●● |
| Legal, fiscal, DPA, texto al cliente | ● | ●●● |
| Prioridades y fechas comerciales | ● | ●●● |
| Onboarding interno (quién responde alertas) | ● | ●●● |

---

## Próximo paso recomendado

Acordar **una fecha** para cerrar Fase 0 (Sentry + webhook de alertas) y **un owner** por fase 1.1 (Stripe) y 1.2 (Resend). El agente puede ayudarte a desgranar cada fila en tareas concretas en el repo cuando lo pidas en modo Agent.

Última actualización: roadmap operativo interno; revisar trimestralmente.
