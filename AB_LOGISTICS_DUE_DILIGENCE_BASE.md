# AB Logistics OS — Documento maestro de due diligence técnica y operativa

**Versión:** base consolidada para auditoría externa  
**Alcance:** repositorio `Scanner` (backend FastAPI, frontend Next.js, Supabase/Postgres, infraestructura documentada y CI).  
**Nota metodológica:** los hallazgos se derivan del análisis estático del código, de `/.env.example`, de `backend/app/core/config.py` y de la documentación en `docs/`. **No se reproducen valores secretos** (claves API, contraseñas, DSN completos); el auditor debe contrastar el despliegue real con las variables listadas en anexo.

---

## 1. Arquitectura técnica y stack

### 1.1 Resumen del stack (versiones verificadas en repo)

| Capa | Tecnología (evidencia) | Observación para auditoría |
|------|------------------------|----------------------------|
| API HTTP | **Python 3.12** (`backend/Dockerfile.prod`), **FastAPI** `0.136.0` (`backend/requirements.txt`), servidor **Gunicorn + UvicornWorker** en imagen prod | No confundir “FastAPI 3.12” con la versión de Python: la runtime es **3.12** y el framework es **FastAPI 0.136**. |
| Frontend | **Next.js 16.1.7**, **React 19.2.3** (`frontend/package.json`) | La documentación comercial o legacy que cite “Next.js 14” queda **desactualizada** respecto al árbol actual. |
| Datos / auth | **Supabase** (URL, anon/service keys, JWKS ES256), **PostgreSQL** vía `DATABASE_URL` + **SQLAlchemy** (`psycopg`) | En **producción** el backend **exige** `DATABASE_URL` no vacía (`ConfigError` en `get_settings()`): no se admite modo exclusivamente REST sin conexión transaccional a Postgres. |
| Colas / workers | **ARQ** + **Redis** (`requirements.txt`, `docker-compose*.yml`, `docs/INFRASTRUCTURE.md`) | Envíos AEAT y trabajos asíncronos dependen de Redis configurado. |
| Monitoreo | **Sentry** (DSN opcional backend y `NEXT_PUBLIC_SENTRY_DSN` frontend) | Muestreo y releases documentados en `.env.example`. |

### 1.2 Infraestructura (Docker, proxy, nube)

- **Desarrollo / stack unificado:** `docker-compose.yml` — servicios **Redis**, **backend** (puerto interno 8000), **frontend** (Next, puerto 3000), **Nginx 1.27-alpine** como reverse proxy (`infrastructure/nginx/default.conf`), healthchecks con `Host` tipo `api.ablogistics-os.com`.
- **Producción VPS / borde:** `docker-compose.prod.yml` — redes segmentadas (**internal** sin salida para Redis; **app**; **edge**), **Caddy 2** como proxy frente a backend/frontend, perfil opcional **Cloudflare Tunnel** (`cloudflared`), contenedor **sentinel-watchdog** (script periódico).
- **Railway:** `backend/railway.json` (build RAILPACK, `uvicorn`, healthcheck `GET /live`), `infra/railway/worker.railway.json`, Terraform comunitario descrito en `docs/INFRASTRUCTURE.md`.
- **Frontend en la nube:** CORS y `TrustedHostMiddleware` incluyen **`.vercel.app`** y dominios oficiales `ablogistics-os.com` / `app.` / `api.` (`config.py`), coherente con despliegues Vercel o híbridos.
- **Google Cloud (GCP):** uso principal en producto vía **Google Maps Platform** y **OAuth** (`Maps_API_KEY`, `GOOGLE_CLIENT_*`, documentación en políticas de privacidad y componentes de mapas). **Alertas de presupuesto GCP** aparecen en roadmap operativo (`docs/operations/ROADMAP_INTEGRACIONES_NEGOCIO.md`) como acción de gobernanza del cliente, no como recurso IaC versionado en este repo.

### 1.3 Estado de módulos de negocio (evidencia en código)

- **Math Engine (`backend/app/core/math_engine.py`):** cálculo determinista de totales fiscales, rectificativas, recargo de equivalencia, integración con emisión de facturas (`facturas_service.py`).
- **Motor fiscal VeriFactu / facturación:** servicios `verifactu_service.py`, `facturas_service.py`, hashing oficial (`verifactu_hashing.py`), PDF/QR (`aeat_qr_service.py`, XML `aeat_xml_service.py`, `suministro_lr_xml.py`).
- **“Truck API” (terminología de negocio):** en el repositorio el dominio de transporte se materializa como **API de portes**, **flota** y **vehículos** (`portes_service.py`, esquemas y migraciones relacionadas con `vehiculo_id`, CO₂, CMR, etc.). No existe un paquete con nombre literal `truck_api`; el alcance equivalente es la **API logística de portes y flota**.

---

## 2. Compliance fiscal (VeriFactu / AEAT)

### 2.1 XAdES-BES y encadenamiento de facturas

- **Firma XAdES-BES:** implementación explícita en `backend/app/core/xades_signer.py` con `signxml.xades.XAdESSigner`, algoritmos **RSA-SHA256** / **SHA256**, modo **enveloped** sobre el nodo raíz `RegistroAlta` conforme a flujo VeriFactu/SuministroLR.
- **Encadenamiento:** doble pista en modelo de datos y servicios:
  - Cadena **hash_registro / hash_anterior** y metadatos secuenciales en emisión (`facturas_service.py`, columnas documentadas en `_PG_FACTURA_EMIT_COLUMNS`).
  - Cadena de **huellas / fingerprint** (`VerifactuService`, `verifactu_hashing.py`) con génesis único por emisor resuelto desde `SecretManagerService` (`VERIFACTU_GENESIS_HASHES` en Vault/AWS Secrets Manager); no hay semilla compartida en `.env`, código o logs.
- **Pruebas automatizadas:** `backend/tests/test_verifactu.py`, `backend/tests/unit/test_verifactu_signature.py`, `backend/tests/unit/test_xades_signer.py` (coherencia XML, presencia de `SignedProperties`, mocks sin red).

### 2.2 Protocolo con la AEAT (SOAP 1.2, mTLS, validación)

- **SOAP 1.2:** documentado y probado en `verifactu_sender.py` (envoltorio, `Content-Type: application/soap+xml`, acción `RegFactuSistemaFacturacion` / registro de facturación).
- **Cliente SOAP:** capa `aeat_soap_client.py` / `aeat_client_py` (Zeep referenciado en `TECHNICAL_AUDIT_REPORT.md` del repo).
- **mTLS:** certificado/clave de cliente vía `AEAT_CLIENT_CERT_PATH`, `AEAT_CLIENT_KEY_PATH`, o `AEAT_CLIENT_P12_PATH` + contraseñas asociadas (`Settings` en `config.py`).
- **Validación XSD:** flag `AEAT_VERIFACTU_XSD_VALIDATE_REQUEST` (por defecto activo en código) y URL opcional `AEAT_VERIFACTU_SUMINISTRO_LR_XSD_URL`.
- **Conmutación test/prod:** `AEAT_VERIFACTU_ENABLED`, `AEAT_VERIFACTU_USE_PRODUCTION`, URLs `AEAT_VERIFACTU_SUBMIT_URL_TEST` / `_PROD`, `AEAT_BLOQUEAR_PROD_EN_DESARROLLO`.

### 2.3 Inalterabilidad de registros y trazabilidad

- **Facturas finalizadas:** flujo de finalización con envío encolado a AEAT (`enqueue_submit_to_aeat`, estados `aeat_sif_estado`, reenvío explícito vía API).
- **Migraciones y políticas:** payloads SQL versionados bajo `backend/.mcp_migration_payloads/` incluyen temas de **inmutabilidad fiscal**, **auditoría**, **fingerprints** y **envíos AEAT** (trazabilidad de esquema).
- **Exportación para inspección:** `exportar_aeat_inspeccion_zip` en `facturas_service.py` (CSV + JSON de cadena de hashes en ZIP).

---

## 3. Seguridad y resiliencia (“El búnker”)

### 3.1 RBAC y Row Level Security (Postgres / Supabase)

- **RBAC aplicación:** roles normalizados `owner`, `traffic_manager`, `driver`, `cliente`, `developer` con compatibilidad legacy (`backend/app/core/rbac.py`), integración con claims JWT / `app_metadata` de Supabase.
- **RLS:** políticas en Postgres gestionadas vía migraciones Supabase; el workflow **Backup Restore Smoke** valida explícitamente que tablas críticas (`facturas_emitidas`, `clientes`, `flota`) tienen **RLS activa** tras restore (`.github/workflows/backup_restore_smoke.yml`).
- **Defensa en profundidad:** uso de **service role** solo donde procede (`deps`), cifrado PII (Fernet `ENCRYPTION_KEY` / rotación documentada en `.env.example`), contraseñas Argon2id con migración lazy desde SHA256 (`auth_service.py`).

### 3.2 Backups automatizados, residencia UE y smoke tests de integridad

- **Backup diario:** `.github/workflows/backup_daily.yml` — Supabase CLI, script `scripts/backup_db.sh`, subida a **Amazon S3 en región UE (`eu-*`)** con credenciales AWS (`BACKUP_*` secrets), SSE-S3 (`AES256`) forzado por objeto o SSE-KMS si se define `BACKUP_S3_KMS_KEY_ID`, y artefacto GitHub de corta retención.
- **Restore smoke semanal:** `.github/workflows/backup_restore_smoke.yml` — valida región UE y cifrado server-side del último objeto S3 antes de descargarlo, restore en Postgres 15 efímero, comprobación de `schema.sql` / `public_data.sql`, conteo mínimo de tablas, datos en `audit_logs`, **RLS** en tablas críticas y tiempos medidos por fase en el job summary.
- **Política BCK-001:** `docs/operations/BACKUP_S3_POLICY.md` documenta residencia de datos, cifrado en reposo, secretos requeridos y evidencia operativa.

### 3.3 Auditoría inmutable (audit logs)

- Migraciones dedicadas a **append-only** y endurecimiento de `audit_logs` (p. ej. payloads `audit_logs_append_only_security.sql`, `audit_logs_select_strict_admin.sql` en `.mcp_migration_payloads/`).
- Los smoke tests asumen **datos presentes** en `public.audit_logs` tras restore, como proxy de integridad del legado auditable.

### 3.4 Rate limiting y protección de superficie fiscal

- Límites por buckets: `AI_RATE_LIMIT`, `MAPS_RATE_LIMIT`, `OCR_RATE_LIMIT` (`.env.example`).
- Middleware fiscal: `fiscal_rate_limit_middleware.py` — límite agregado (p. ej. 300/min por tenant) en rutas de envío AEAT/VeriFactu.
- ESG público: límite configurable `ESG_PUBLIC_VERIFY_RATELIMIT` (`public_esg.py`).

---

## 4. GTM y operaciones

### 4.1 Correo transaccional (Resend, SPF/DKIM/DMARC)

- Variables: `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS`, `EMAILS_FROM_EMAIL`, `EMAIL_FROM_NAME`, estrategias `EMAIL_STRATEGY_INVOICE` y `EMAIL_STRATEGY_TRANSACTIONAL` (`smtp` | `resend` | `auto`) — ver `.env.example` y `docs/operations/EMAIL_STRATEGY.md`.
- **SPF/DKIM/DMARC:** configuración DNS en lado del **dominio remitente** (runbook en roadmap Fase 1.2); el código asume remitente verificado en Resend.
- **Seguridad coordinada:** `SECURITY_CONTACT_EMAIL` y mención RFC 9116 en documentación de infraestructura.

### 4.2 Pasarela de pagos (Stripe) y webhooks

- Producto: precios/planes mapeados a variables `STRIPE_PRICE_*` / alias Due Diligence (`STRIPE_PRICE_COMPLIANCE`, etc.) en `config.py`.
- **Webhooks:** rutas `/webhooks/stripe` y `/payments/stripe/webhook` (`backend/app/api/v1/webhooks/stripe.py`) — cuerpo **raw**, cabecera `Stripe-Signature`, verificación mediante `stripe.Webhook.construct_event` y secreto vía `SecretManagerService` / `STRIPE_WEBHOOK_SECRET` (tests mockean el secreto en `conftest.py`).
- **GoCardless (pagos / datos bancarios):** `GOCARDLESS_*` y webhooks con HMAC documentado en `Settings`; endpoints bajo `banking.py` cuando credenciales están configuradas.

### 4.3 Control de costes y abuso

- **APIs de terceros:** rate limits declarados para IA, mapas y OCR (env).
- **Maps / GCP:** roadmap explicita presupuestos y alertas de billing en consola Google como responsabilidad operativa (`ROADMAP_INTEGRACIONES_NEGOCIO.md` §2.2).
- **Observabilidad:** Sentry backend/frontend, opcional `DISCORD_WEBHOOK_URL` en `.env.example` para alertas operativas.

---

## 5. Roadmap V2.0 (Fase 5 — visión alineada al repo)

Los hitos siguientes están **parcialmente implementados** o **planificados** en documentación/código; el auditor debe distinguir “en código” vs “en roadmap”.

| Hito | Estado en repo | Notas |
|------|-----------------|-------|
| **Banking sync** | **Implementado (base):** `backend/app/api/v1/banking.py`, `banking_orchestrator`, OAuth callback en frontend (`bancos/callback`) | Requiere `GOCARDLESS_SECRET_ID`, `GOCARDLESS_SECRET_KEY`, tokens y webhooks en prod. |
| **Carrier APIs** | Evolución natural del módulo **portes / CMR / integraciones**; sin conector genérico “carrier” único versionado | Roadmap de integraciones en `docs/operations/ROADMAP_INTEGRACIONES_NEGOCIO.md`. |
| **Financial AI Advisor (“LogisAdvisor”)** | Referencias a producto Stripe `STRIPE_PRICE_LOGISADVISOR_IA_PRO`, reconciliación híbrida en banking | Depende de presupuesto IA, LiteLLM/proveedores y límites ya previstos en env. |

---

## 6. Análisis DAFO técnico

### Fortalezas

- **Cumplimiento fiscal avanzado:** XAdES-BES, SOAP 1.2, mTLS, validación XSD, encadenamiento de hashes, estados AEAT persistidos, exportación para inspección y batería de tests.
- **Seguridad enterprise:** RLS validada en CI post-restore, RBAC explícito, cookies seguras en prod, hosts de confianza, CORS estricto en producción, cifrado PII, webhooks firmados (Stripe/GoCardless), secret manager abstraíble (`SECRET_MANAGER_BACKEND` en `.env.example`).
- **Operaciones:** backups automatizados a S3 + job de integridad; documentación de DRP/infra (`docs/operations`, `docs/INFRASTRUCTURE.md`).

### Debilidades

- **Marca y madurez de mercado:** producto relativamente nuevo; dependencia de ejecución correcta de DNS, certificados AEAT y procesos manuales del titular.
- **Complejidad de despliegue:** producción exige Postgres + Redis + secretos coherentes; Terraform Railway es **provider comunitario** (riesgo de mantenimiento).
- **Discrepancia documental:** material que cite “Next.js 14” frente a **Next 16** en `package.json`.

### Oportunidades

- **Regulación AEAT / VeriFactu:** demanda estructural de trazabilidad e integridad en facturación B2B logística.
- **ESG y huella:** módulos CO₂, certificaciones y verificación pública acotada por rate limit — alineación con reporting **ESG** y due diligence de cadena de suministro.
- **Banking + IA:** diferenciación en conciliación y advisor financiero si se cierra gobernanza de datos y coste.

### Amenazas

- **ERPs legacy y lock-in:** integración competirá con sistemas incumbentes; APIs carrier heterogéneas aumentan coste de mantenimiento.
- **Volatilidad de coste API:** Maps (GCP), LLM OCR, y modelos de advisor — sin cupos estrictos por tenant en todo el código base (parcialmente cubierto por rate limits globales/buckets).
- **Disponibilidad AEAT / certificados:** incidentes de red o caducidad de certificado cliente impactan envíos SIF pese a colas y reintentos.

---

## Anexo A — Variables de entorno relevantes (solo nombres; sin valores)

Origen principal: `/.env.example` y `backend/app/core/config.py`.

**Core / Supabase / DB:** `ENVIRONMENT`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`, `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, `SESSION_SECRET_KEY`, `ENCRYPTION_KEY`, `SECRET_MANAGER_BACKEND`, …

**AEAT VeriFactu:** `AEAT_VERIFACTU_ENABLED`, `AEAT_VERIFACTU_USE_PRODUCTION`, `AEAT_VERIFACTU_SUBMIT_URL_TEST`, `AEAT_VERIFACTU_SUBMIT_URL_PROD`, `AEAT_CLIENT_*`, `AEAT_VERIFACTU_WSDL_URL`, `AEAT_VERIFACTU_XSD_VALIDATE_REQUEST`, `VERIFACTU_SERIE_FACTURA`, `VERIFACTU_SERIE_RECTIFICATIVA`, …

**Correo:** `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS`, `EMAIL_STRATEGY_*`, `EMAILS_FROM_EMAIL`, …

**Pagos:** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_*`, `GOCARDLESS_*`, …

**Maps / OAuth / IA:** `Maps_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `AI_RATE_LIMIT`, …

**GitHub Actions backup:** `SUPABASE_ACCESS_TOKEN`, `SUPABASE_PROJECT_REF`, `SUPABASE_DB_PASSWORD`, `BACKUP_AWS_*`, `BACKUP_S3_BUCKET`, `BACKUP_S3_PREFIX`, `BACKUP_S3_KMS_KEY_ID` (opcional).

---

## Anexo B — Rutas de evidencia rápida para auditores

| Tema | Ruta |
|------|------|
| Configuración y gates de producción | `backend/app/core/config.py` |
| Firma XAdES | `backend/app/core/xades_signer.py` |
| Envío AEAT SOAP/mTLS | `backend/app/services/verifactu_sender.py` |
| Emisión y columnas factura | `backend/app/services/facturas_service.py` |
| Webhook Stripe | `backend/app/api/v1/webhooks/stripe.py` |
| RBAC | `backend/app/core/rbac.py` |
| Backup / restore CI | `.github/workflows/backup_daily.yml`, `backup_restore_smoke.yml` |
| Docker prod | `docker-compose.prod.yml`, `backend/Dockerfile.prod`, `frontend/Dockerfile.prod` |
| Informe técnico previo | `TECHNICAL_AUDIT_REPORT.md` |

---

*Documento generado a partir del estado del repositorio en la fecha de elaboración de la sesión. Las afirmaciones sobre certificados, DNS en producción y modos AEAT “live” deben verificarse contra el entorno desplegado y la documentación fiscal externa (AEAT) vigente.*
