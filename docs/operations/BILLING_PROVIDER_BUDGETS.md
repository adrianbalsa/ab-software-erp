# BILLING-001: presupuestos, hard limits y alertas por proveedor (Fase 2.4)

## Objetivo

Definir **umbrales de gasto en la nube y en APIs de terceros** (AWS, Google Cloud / Maps, OpenAI y afines), **alertas 50 / 80 / 100 %**, y la **respuesta operativa** (soft vs hard) sin depender de una sola persona. Complementa las **cuotas por tenant** en aplicación (`tenant_monthly_usage`, planes en `backend/app/core/plans.py`) descritas en `STRIPE_BILLING.md`.

## Definiciones: soft vs hard

| Tipo | Ámbito | Ejemplo | Acción típica |
|------|--------|---------|----------------|
| **Soft** | Aviso antes del corte | Presupuesto al 80 %, cuota interna al 80 % | Revisar tendencia, avisar producto/soporte, optimizar caché o desactivar features no críticas. |
| **Hard** | Corte o bloqueo | Presupuesto 100 % con acción *stop* en AWS Budgets; API key sin saldo; límite duro de org en OpenAI | Escalar a on-call P2; congelar nuevas llamadas costosas; plan de downgrade o recarga de facturación; comunicación a stakeholders. |

Las **cuotas SaaS por empresa** (Maps, OCR, IA) son *soft/hard de producto*; los **budgets de facturación del proveedor** son *soft/hard de infraestructura*. Ambos deben tener owner y canal de alerta.

## Owner y canales

- **Owner primario de coste proveedor:** Platform / FinOps (según `OPS_001_TOPOLOGIA_PLATAFORMA.md`).
- **Canal mínimo:** mismo webhook/canal que alertas operativas (`ALERT_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`, email de facturación GCP/AWS si aplica).
- **On-call:** enlazar incidentes de sobrecoste con severidad en `ON_CALL_RUNBOOK.md` (P3 preventiva si solo umbral 50 %; P2 si 100 % o riesgo de interrupción).

## 1. AWS

1. **Billing → Budgets**  
   Crear un presupuesto mensual (o anual con prorrateo) alineado al forecast de la cuenta (Railway/ECS/RDS/S3/Secrets/transferencia).
2. **Umbrales de alerta**  
   Configurar notificaciones al **50 %, 80 % y 100 %** del presupuesto (correo + SNS → Slack/Discord si está cableado).
3. **Cost Anomaly Detection** (recomendado)  
   Suscripción a informes de anomalía para picos inesperados (p. ej. transferencia o API mal limitada).
4. **Acciones opcionales al 100 %**  
   Evaluar *Budget action* (solo tras revisión legal/contractual): notificación vs restricción de recursos; en muchos equipos el hard limit es **manual** tras alerta.

**Evidencia:** export PDF o captura de la regla de budget + lista de destinatarios/SNS (sin secretos); archivar en almacén interno de cumplimiento o ticket de change management (no en repositorio git público).

## 2. Google Cloud Platform (Maps, APIs GCP, facturación vinculada)

1. **Billing → Budgets & alerts**  
   Presupuesto por proyecto o por etiqueta (`maps`, `vertex`, etc.) con alertas **50 / 80 / 100 %**.
2. **Cuotas de API**  
   En *APIs & Services → Quotas*, revisar límites de **Routes / Maps** y solicitar tope máximo acorde al riesgo aceptado (evita sorpresas además del rate limit de aplicación).
3. **BigQuery / egress**  
   Si hay pipelines, budget específico o alerta por SKU.

**Evidencia:** igual que AWS (captura + destino interno).

## 3. OpenAI (y proveedores LLM equivalentes)

1. **Organization → Settings → Limits**  
   Definir **límite mensual de uso** (hard de org) y revisión de **rate limits** por tier.
2. **Billing → Usage alerts**  
   Activar alertas de consumo / umbral de facturación según lo que ofrezca el panel en el momento del despliegue.
3. **Claves**  
   Rotación y separación: clave de producción solo en `SecretManagerService`; nunca en logs.

**Evidencia:** captura de pantalla de límites configurados (sin mostrar la clave).

## 4. Otros (Anthropic, Azure OpenAI, Resend, etc.)

Repetir el mismo patrón: **presupuesto o alerta nativa del proveedor** + **owner**. Si el proveedor no ofrece budget, usar **suma en hoja de control mensual** + alerta desde export CSV o billing email.

## 5. Alineación con el producto (AB Logistics OS)

- **Rate limits y cuotas tenant:** `TenantRateLimitMiddleware`, buckets AI/Maps/OCR, tabla `tenant_monthly_usage` (ver `STRIPE_BILLING.md`).
- **Runbook si un tenant agota cuota:** mismo documento, sección *Runbook de incidente billing*.
- **No sustituye** budgets de nube: un bug que llame en bucle a Maps puede quemar cuota GCP aunque los tenants estén dentro de plan.

## 6. Runbook: alerta de sobrecoste (plantilla)

1. **Acuse:** responder en el hilo de alerta con hora UTC y enlace al budget/disparador.
2. **Clasificar:** ¿es umbral 50/80 % (planificar) o 100 % / anomalía (actuar ya)?
3. **Medir:** consola del proveedor → desglose por servicio/SKU/proyecto; correlacionar con deploys y picos de tráfico (`request_id`, Sentry).
4. **Mitigar:** desactivar feature flag costosa, subir caché TTL, corregir bug, pausar worker que dispare llamadas externas.
5. **Comunicar:** producto/cliente solo si hay impacto en SLA o facturación passthrough.
6. **Cerrar:** ticket con causa, coste estimado evitado o incurrido, y acción preventiva (nuevo budget, nuevo límite, ticket de código).

## 7. Registro de evidencia (go-live / auditoría)

| Artefacto | Dónde guardarlo |
|-----------|-----------------|
| Capturas budgets AWS/GCP | Carpeta interna de cumplimiento o gestor documental (no git público). |
| Lista de umbrales acordados | Este repo: actualizar tabla en PR cuando cambie el forecast. |
| Post-mortem sobrecoste | Mismo sistema que incidentes (`ON_CALL_RUNBOOK.md`). |

**Criterio de cierre operativo:** existen budgets o alertas equivalentes en **AWS, GCP (incl. Maps) y OpenAI** (u otros LLM en uso), con **notificaciones 50/80/100 %**, **owner** y **runbook** ejecutado al menos una vez en simulacro o revisión documentada.

## Referencias

- `docs/operations/STRIPE_BILLING.md` — billing SaaS, webhooks, cuotas internas.
- `docs/operations/ON_CALL_RUNBOOK.md` — severidad y handoff.
- `docs/operations/OPS_001_TOPOLOGIA_PLATAFORMA.md` — variables y superficies.
