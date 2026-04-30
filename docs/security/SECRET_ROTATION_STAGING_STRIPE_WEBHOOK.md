# Rotación controlada en staging — `STRIPE_WEBHOOK_SECRET`

Objetivo: cambiar el **signing secret** del webhook de Stripe en entorno **staging** sin downtime prolongado, con validación y rollback en menos de 15 minutos.

Referencias de código:

- Validación de firma y secreto: `backend/app/services/stripe_service.py` (`get_secret_manager().get_stripe_webhook_secret()`).
- Rutas HTTP canónicas (prefijo `/api/v1`):

```19:24:backend/app/api/v1/webhooks/stripe.py
@router.post("/webhooks/stripe")
@router.post(
    "/payments/stripe/webhook",
```

URLs efectivas (staging):

- `POST https://<API_STAGING>/api/v1/webhooks/stripe`
- Alias legacy: `POST https://<API_STAGING>/api/v1/payments/stripe/webhook` (configura **solo uno** en Stripe Dashboard para evitar duplicados).

---

## Pre-checklist (antes de tocar nada)

1. Confirmar que staging usa cuenta Stripe **test mode** (no live keys).
2. Anotar `rotation_id` (ej. `rot-stripe-wh-staging-YYYY-MM-DD`).
3. Ventana: 15–30 minutos; avisar si hay checkout activo en staging.

---

## Paso A — Generar nuevo signing secret en Stripe

1. Stripe Dashboard → **Developers** → **Webhooks**.
2. Abrir el endpoint que apunta a tu API staging (`/api/v1/webhooks/stripe`).
3. **Reveal** / **Roll secret** (según UI): obtendrás un nuevo valor `whsec_...`.
4. **No pegues el valor en chat ni en commits.** Solo en el gestor de secretos del entorno (Railway / Vercel / GitHub Secrets / Vault / AWS SM según tu despliegue).

---

## Paso B — Actualizar secreto en el runtime de staging

1. Actualizar variable de entorno `STRIPE_WEBHOOK_SECRET` con el **nuevo** `whsec_...`.
2. Redeploy / restart del servicio backend que ejecuta FastAPI (los procesos cargan `SecretManagerService` al arranque; la forma más segura es redeploy).
3. Esperar health OK:

   - `GET https://<API_STAGING>/live`
   - `GET https://<API_STAGING>/health` o `/ready` según tu configuración.

---

## Paso C — Validación funcional mínima

1. En Stripe Dashboard → el mismo webhook → **Send test webhook** (evento ligero, p. ej. `checkout.session.completed` o el que uses).
2. Esperado: respuesta **2xx** desde tu API y logs sin error de firma.
3. Si el dashboard muestra **firma inválida** o **401/400**:

   - Verifica que el secreto en runtime coincide con el mostrado para ese endpoint en Stripe.
   - Verifica que no hay **dos endpoints** en Stripe apuntando a URLs distintas con secretos distintos.

---

## Paso D — Revocación del secreto anterior

1. Tras 24–72 h de estabilidad sin errores de webhook en staging, eliminar/invalidar el signing secret antiguo en Stripe **solo si** la UI lo permite sin romper el endpoint activo (según flujo de Stripe).
2. Si Stripe mantiene ambos durante un tiempo, deja constancia en el log de rotación.

---

## Rollback rápido

1. Restaurar `STRIPE_WEBHOOK_SECRET` al valor **anterior** (guardado en gestor de secretos / backup interno).
2. Redeploy backend staging.
3. Re-enviar **Send test webhook** hasta respuesta 2xx.

---

## Evidencia para DD (rellenar tras ejecución real)

Copiar a `docs/security/SECRET_ROTATION_LOG_STRIPE_WEBHOOK_STAGING.md` (crear el día que ejecutes):

| Campo | Valor |
| --- | --- |
| rotation_id |  |
| fecha UTC |  |
| entorno | staging |
| secreto (nombre lógico) | STRIPE_WEBHOOK_SECRET |
| stripe webhook endpoint id | (ID del endpoint en Dashboard, no el secret) |
| validación | Send test webhook → 2xx |
| resultado | success / rolled_back |
| notas |  |
