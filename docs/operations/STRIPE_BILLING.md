# Stripe Billing — cierre operativo (AB Logistics OS)

Este documento describe la **configuración mínima** para producción y el **contrato de webhooks** entre Stripe y la API.

## Variables de entorno

| Variable | Uso |
|----------|-----|
| `STRIPE_SECRET_KEY` | API secreta (vía `SecretManagerService` en producción). |
| `STRIPE_WEBHOOK_SECRET` | **Signing secret** del endpoint de webhooks en Stripe Dashboard. |
| `STRIPE_PRICE_STARTER` / `STRIPE_PRICE_PRO` / `STRIPE_PRICE_ENTERPRISE` | IDs de precio (`price_…`) alineados a los productos SaaS. |
| `PUBLIC_APP_URL` | Origen del frontend (checkout success/cancel, portal return). |
| `STRIPE_SUCCESS_URL` / `STRIPE_CANCEL_URL` / `STRIPE_PORTAL_RETURN_URL` | Opcionales; por defecto se derivan de `PUBLIC_APP_URL`. |

## Stripe Dashboard

1. **Productos y precios**  
   Crear tres precios recurrentes (Starter / Pro / Enterprise) y copiar los `price_*` a las variables anteriores.

2. **Customer portal**  
   Activar el [Billing portal](https://dashboard.stripe.com/settings/billing/portal) (métodos de pago, facturas, cancelación). Sin portal configurado, las sesiones de portal pueden fallar.

3. **Webhooks**  
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

## Checklist previo a go-live

- [ ] Precios `price_*` en entorno de despliegue.
- [ ] Webhook en modo **live** con URL HTTPS y secret en vault/env.
- [ ] Portal de facturación revisado (textos, datos de empresa, impuestos si aplica).
- [ ] `PUBLIC_APP_URL` apunta al dominio real del frontend.
- [ ] Prueba de checkout + portal en **test mode** antes de alternar claves live.
