# Estrategia de correo (Resend + SMTP)

AB Logistics OS permite definir el proveedor por tipo de correo sin tocar código.

## Variables

- `EMAIL_STRATEGY_INVOICE`: `smtp` | `resend` | `auto`
- `EMAIL_STRATEGY_TRANSACTIONAL`: `resend` | `smtp` | `auto`

## Reglas de resolución

- **`EMAIL_STRATEGY_INVOICE`**
  - `smtp`: exige `SMTP_HOST`, `SMTP_PORT`, `EMAILS_FROM_EMAIL`.
  - `resend`: exige `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS`.
  - `auto`: prioriza SMTP; si no está disponible, usa Resend.

- **`EMAIL_STRATEGY_TRANSACTIONAL`** (reset password, onboarding, welcome enterprise, ESG)
  - `resend`: exige `RESEND_API_KEY`.
  - `smtp`: exige `SMTP_HOST`, `SMTP_PORT`, `EMAILS_FROM_EMAIL`.
  - `auto`: prioriza Resend; si no está disponible, usa SMTP.

## Recomendación operativa

- **Producción B2B típica**
  - `EMAIL_STRATEGY_INVOICE=smtp`
  - `EMAIL_STRATEGY_TRANSACTIONAL=resend`

Esto mantiene facturación en canal corporativo/contable y comunicaciones de producto en Resend.

## Verificación rápida

1. Emitir factura y verificar envío (ruta `/api/facturas/...`).
2. Ejecutar flujo de recuperación de contraseña.
3. Revisar logs y Sentry (`email.smtp` / `email.resend` spans).
4. Confirmar que auditoría de envío conserva el canal efectivo (`smtp` o `resend`).
