# VeriFactu — runbook operativo end-to-end (handover)

Resumen para **guardias y equipo externo**: cadena fiscal en la app, envío AEAT y reintentos. Detalle normativo: documentación AEAT y legal interna.

## 1. Datos y cadena en base de datos

- **Génesis:** hash inicial por emisor (`VERIFACTU_GENESIS_HASH` / mapa por empresa). Producción con AEAT activo exige génesis resuelto antes de enviar (`verifactu_genesis`, arranque API).
- **Emisión:** facturas bloqueadas (`bloqueado`), `huella_hash` / cadena encadenada (`VerifactuService`, `facturas_service`).
- **Finalización:** pasa a `is_finalized`, dispara jobs VeriFactu según configuración; columnas `aeat_sif_*` reflejan estado SIF.

## 2. Envío a la AEAT

- **Código principal:** `backend/app/services/verifactu_sender.py` (SOAP, mTLS, Zeep), XML `suministro_lr_xml.py`, firma XAdES.
- **Trazas:** `public.verifactu_envios` (intentos, `http_status`, errores).
- **Homologación / pruebas:** `docs/operations/AEAT_VERIFACTU_HOMOLOGACION.md`.
- **Certificados mTLS:** `docs/operations/MTLS_CERTIFICATE_RENEWAL.md`, chequeo `checks.aeat_mtls_certificates` en `GET /health/deep`.

## 3. Reintentos y cola

- Reintentos automáticos ante `429` / `5xx` / transporte (límite `AEAT_HTTP_MAX_ATTEMPTS`).
- **No reintentar a ciegas** ante `XSD_REQUEST`, `CERT`, `XADES`, `SOAP_MALFORMED` — incidencia de producto/datos.
- Reintento operativo agrupado: `POST /api/v1/verifactu/retry-pending` (detalle en `AEAT_VERIFACTU_HOMOLOGACION.md`, sección de reintentos).

## 4. Idempotencia y webhooks

- Eventos externos críticos (p. ej. Stripe): `webhook_events` + idempotencia; ver `STRIPE_BILLING.md` y código `webhook_idempotency.py`.

## 5. Qué tocar en incidente (orden)

1. Clasificar: ¿cadena, certificado, XML, transporte AEAT, o dato fiscal incorrecto?
2. `/health/deep` + `verifactu_envios` + `facturas.aeat_sif_*` para la factura afectada.
3. Seguir **`AEAT_VERIFACTU_HOMOLOGACION.md`** § Runbook de incidente AEAT.
4. Cerrar con acta: `evt_*` o IDs internos, causa, acción, riesgo residual.

## Referencias de código (orientación)

| Tema | Ruta |
|------|------|
| Envío SOAP | `app/services/verifactu_sender.py` |
| Génesis | `app/services/verifactu_genesis.py` |
| Hash / cadena | `app/services/verifactu_service.py` |
| Hashing oficial | `app/core/verifactu_hashing.py` |
| Health profundo | `app/core/health_checks.py` |
