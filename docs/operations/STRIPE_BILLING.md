# Stripe Billing — cierre operativo (AB Logistics OS)

Este documento describe la **configuración mínima** para producción y el **contrato de webhooks** entre Stripe y la API.

## Variables de entorno

| Variable | Uso |
|----------|-----|
| `STRIPE_SECRET_KEY` | API secreta (vía `SecretManagerService` en producción). |
| `STRIPE_WEBHOOK_SECRET` | **Signing secret** del endpoint de webhooks en Stripe Dashboard. |
| `STRIPE_PRICE_STARTER` / `STRIPE_PRICE_PRO` / `STRIPE_PRICE_ENTERPRISE` | IDs de precio (`price_…`) alineados a los productos SaaS (nombres comerciales **Compliance** / **Finance** / **Enterprise**; catálogo orientativo **39 € / 149 € / 399 €** / mes + IVA). |
| `STRIPE_PRICE_OCR_PACK` | Add-on **OCR Pack** (~15 €/mes, volumen extra documentos). |
| `STRIPE_PRICE_WEBHOOKS_B2B_PREMIUM` | Add-on **Webhooks B2B Premium** (~49 €/mes). |
| `STRIPE_PRICE_LOGISADVISOR_IA_PRO` | Add-on **LogisAdvisor IA Pro** (~29 €/mes). |
| `PUBLIC_APP_URL` | Origen del frontend (checkout success/cancel, portal return). |
| `STRIPE_SUCCESS_URL` / `STRIPE_CANCEL_URL` / `STRIPE_PORTAL_RETURN_URL` | Opcionales; por defecto se derivan de `PUBLIC_APP_URL`. |

## Stripe Dashboard

1. **Productos y precios**  
   Crear precios recurrentes para **Compliance**, **Finance** y **Enterprise** (slugs técnicos `starter` / `pro` / `enterprise`) y, si aplica, líneas de add-on (OCR Pack, Webhooks B2B Premium, LogisAdvisor IA Pro). Copiar los `price_*` a las variables `STRIPE_PRICE_*`.

2. **Frontend público (opcional)**  
   Para el bloque de precios en la landing, definir `NEXT_PUBLIC_STRIPE_PRICE_STARTER`, `NEXT_PUBLIC_STRIPE_PRICE_PRO` y `NEXT_PUBLIC_STRIPE_PRICE_ENTERPRISE` con los mismos `price_*` que usa el checkout.

3. **Customer portal**  
   Activar el [Billing portal](https://dashboard.stripe.com/settings/billing/portal) (métodos de pago, facturas, cancelación). Sin portal configurado, las sesiones de portal pueden fallar.

4. **Webhooks**  
   - URL: `https://<API_HOST>/api/v1/webhooks/stripe`  
   - Eventos mínimos recomendados:
     - `checkout.session.completed`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.paid`  
   - Guardar el **signing secret** en `STRIPE_WEBHOOK_SECRET`.

## Comportamiento en código

- **Firma**: `stripe.Webhook.construct_event` rechaza payloads no firmados.
- **Idempotencia**: eventos con `id` (`evt_…`) se registran; reenvíos duplicados responden `{"received": true, "duplicate": true}` sin repetir efectos en base de datos.
- **Checkout**: `client_reference_id` / `metadata.empresa_id` deben identificar la empresa tenant.
- **Suscripción**: `customer.subscription.updated` sincroniza plan cuando el `price_id` coincide con `STRIPE_PRICE_*` o hay `plan_type` en metadata.

## Smoke test (Stripe CLI)

```bash
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
```

Comprobar logs y fila `empresas` (plan, `stripe_customer_id`, `stripe_subscription_id`).

## Checks operativos de billing

### Diario

- Revisar eventos fallidos en Stripe Dashboard para el endpoint `https://<API_HOST>/api/v1/webhooks/stripe`.
- Confirmar ausencia de picos de `invoice.payment_failed`, `customer.subscription.deleted` y errores `400/503` en la API.
- Revisar tenants con `subscription_status` no activo (`past_due`, `unpaid`, `canceled`) y decidir comunicacion o downgrade.
- Validar que no hay errores de `STRIPE_WEBHOOK_SECRET` o firma en logs.

### Semanal

- Comparar conteo de suscripciones activas en Stripe contra empresas activas con `stripe_subscription_id`.
- Revisar que los `price_*` configurados siguen apuntando a productos correctos y modo correcto (`test` vs `live`).
- Ejecutar smoke en test mode tras cambios de checkout, portal, planes o secretos.
- Revisar cuotas mensuales de coste externo (`maps_calls_month`, `ocr_pages_month`, `ai_tokens_month`) para detectar tenants cerca de limite.

Consulta sugerida para cuotas:

```sql
select
  empresa_id,
  period_yyyymm,
  meter,
  used_units,
  limit_units,
  round((used_units::numeric / nullif(limit_units, 0)) * 100, 2) as pct_used
from public.tenant_monthly_usage
where period_yyyymm = to_char(now(), 'YYYY-MM')
order by pct_used desc nulls last;
```

### Cierre mensual

- Confirmar que facturas Stripe del mes se han emitido/cobrado o quedan clasificadas.
- Revisar tenants con cuota agotada (`monthly_cost_quota_exceeded`) y decidir upsell, add-on o excepcion manual.
- Exportar evidencia de MRR, churn, add-ons activos y eventos webhook relevantes.
- Revisar que el catalogo de precios comercial coincide con `backend/app/core/plans.py`.

## Runbook de incidente billing

1. Si Stripe no puede entregar webhooks, revisar firma/secret, disponibilidad API y reintentos pendientes en Dashboard.
2. Si checkout falla, validar `STRIPE_SECRET_KEY`, `STRIPE_PRICE_*`, `PUBLIC_APP_URL` y URLs de success/cancel.
3. Si un tenant queda con plan incorrecto, comparar evento Stripe, metadata `empresa_id` y fila `empresas`; corregir con trazabilidad administrativa.
4. Si se agota una cuota critica por error, revisar `tenant_monthly_usage`, plan normalizado y consumo reciente antes de tocar limites.
5. Cerrar el incidente con evento Stripe afectado (`evt_*`), empresa, impacto comercial, acciones y necesidad de credito de servicio si aplica.

## Presupuestos en proveedores cloud (Fase 2.4)

Los límites de **Stripe y cuotas por tenant** no sustituyen los **budgets de AWS, GCP (Maps) ni OpenAI**. Umbrales **50 / 80 / 100 %**, owner y respuesta ante sobrecoste: ver **`docs/operations/BILLING_PROVIDER_BUDGETS.md`**.

## Checklist previo a go-live

- [ ] Precios `price_*` en entorno de despliegue.
- [ ] Webhook en modo **live** con URL HTTPS y secret en vault/env.
- [ ] Portal de facturación revisado (textos, datos de empresa, impuestos si aplica).
- [ ] `PUBLIC_APP_URL` apunta al dominio real del frontend.
- [ ] Prueba de checkout + portal en **test mode** antes de alternar claves live.
- [ ] Dashboard de eventos fallidos y suscripciones `past_due/unpaid` revisado.
- [ ] Cuotas mensuales `maps_calls_month`, `ocr_pages_month` e `ai_tokens_month` visibles para soporte/producto.
