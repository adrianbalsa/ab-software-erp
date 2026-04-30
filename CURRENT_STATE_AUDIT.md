# CURRENT STATE AUDIT (Abril 2026)

Documento factual del estado actual del repositorio `Scanner`, construido a partir de código y configuración presentes en el árbol de trabajo.

## 1) Infraestructura y Stack (Topología actual)

### 1.1 Topología de despliegue (Docker Compose + Nginx + Supabase + Redis)

- Orquestación principal en `docker-compose.yml` con 4 servicios: `redis`, `backend`, `frontend`, `nginx`.
- Orquestación productiva en `docker-compose.prod.yml`:
  - extiende los 4 servicios base.
  - añade servicio `certbot` para renovación periódica (`certbot renew ...; sleep 12h`).
  - usa volúmenes persistentes `letsencrypt_data` y `certbot_www`.
- Red Docker única: `ab_logistics_net` (driver `bridge`).
- Volúmenes definidos:
  - `redis_data`, `backend_logs`, `frontend_logs`, `nginx_logs`, `reports_tmp`.
  - en prod además `letsencrypt_data`, `certbot_www`.

### 1.2 Flujo de tráfico HTTP(S)

- `nginx` expone `80:80` y `443:443`.
- `80`:
  - sirve `/.well-known/acme-challenge/` para Certbot.
  - redirige todo a HTTPS (`301`).
- `443`:
  - TLS con certificados en `/etc/letsencrypt/live/default/`.
  - proxy `/api/`, `/reports/`, `/health`, `/ready` -> `backend:8000`.
  - proxy `/` -> `frontend:3000`.
- Upstreams definidos:
  - `backend_upstream` (`backend:8000`, `keepalive 32`).
  - `frontend_upstream` (`frontend:3000`, `keepalive 32`).

### 1.3 Backend runtime

- Imagen: `python:3.12-slim-bookworm` (multi-stage `builder` + `runner`).
- Servidor: `gunicorn app.main:app` con `uvicorn.workers.UvicornWorker`.
- Puerto: `8000`.
- Variables relevantes en compose:
  - `ENVIRONMENT`, `DATABASE_URL`, `REDIS_URL`.
  - credenciales Supabase (`SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, etc.).
  - claves IA (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`).
  - configuración AEAT (`AEAT_CERTS_DIR`, `AEAT_P12_PATH`, `AEAT_CERT_PASSPHRASE`).
- Dependencia explícita de Redis (`depends_on: redis: service_healthy`).

### 1.4 Frontend runtime

- Imagen: `node:20-alpine` (deps/builder/runner).
- Framework: `next` `16.1.7`, `react` `19.2.3`.
- Puerto: `3000`.
- Variables build-time públicas (`NEXT_PUBLIC_*`) y runtime (`INTERNAL_API_BASE_URL=http://backend:8000`).

### 1.5 Redis y Supabase

- Redis:
  - `redis:7-alpine`, `appendonly yes`, volumen persistente `redis_data`.
  - usado para rate limiting compartido (cuando `REDIS_URL` está definido), cache y colas según código/config.
- Supabase:
  - no existe servicio Supabase local en `docker-compose`.
  - integración por variables (`SUPABASE_URL`, `SUPABASE_*`) y migraciones SQL en `supabase/migrations/`.
  - RLS explícito en migraciones (`public.app_current_empresa_id()`).

### 1.6 Librerías y versiones declaradas (estado actual)

- Backend (`backend/requirements.txt`):
  - framework/API: `fastapi==0.136.0`, `starlette==0.49.1`, `uvicorn==0.27.0`, `gunicorn==25.3.0`.
  - rate limit: `slowapi==0.1.9`, `limits==5.8.0`, `redis==5.3.1`.
  - fiscal/AEAT/XML: `zeep==4.2.1`, `signxml==4.4.0`, `xmlschema==3.3.1`, `lxml==6.1.0`, `cryptography==46.0.7`.
  - IA: `litellm==1.83.14`, `openai==2.24.0`, `anthropic` (sin pin), `google-genai` (sin pin), `tiktoken==0.12.0`.
  - observabilidad: `sentry-sdk[fastapi]==2.56.0`.
  - tests: `pytest==9.0.3`, `pytest-asyncio==1.3.0`, `pytest-cov==6.0.0`.
- Frontend (`frontend/package.json`):
  - `next` `16.1.7`, `react`/`react-dom` `19.2.3`.
  - observabilidad: `@sentry/nextjs ^10.49.0`, OpenTelemetry packages.
  - data/auth: `@supabase/supabase-js ^2.101.1`, `@supabase/ssr ^0.10.0`, `@tanstack/react-query ^5.100.6`.
  - tests: `vitest ^4.1.5`, `@playwright/test ^1.59.1`.

## 2) Seguridad y Frontera API

### 2.1 Stack de middlewares activo (create_app)

`backend/app/main.py` registra, en este orden de adición:

- `SessionMiddleware`
- `JsonAccessLogMiddleware`
- `RequestIdMiddleware`
- `SecurityHeadersMiddleware`
- `CORSMiddleware`
- `IdempotencyMiddleware`
- `SlowRequestLogMiddleware`
- `SkipOptionsSlowAPIMiddleware`
- `GlobalIPRateLimitMiddleware`
- `TenantRateLimitMiddleware`
- `BIRateLimitMiddleware`
- `AuthLoginRateLimitMiddleware`
- `EndpointCostRateLimitMiddleware`
- `FiscalVerifactuRateLimitMiddleware`
- `TrustedHostMiddleware`
- `LoginDebugPrintMiddleware`
- `TenantRBACContextMiddleware`
- `AuditLogMiddleware`
- `GlobalExceptionMiddleware`
- `HealthCheckBypassMiddleware`

También define:
- `/openapi.json` y alias `/api/v1/openapi.json`.
- docs habilitadas (`/docs`, `/redoc`).

### 2.2 CORS (validación real efectiva)

- `Settings` calcula:
  - `CORS_ALLOW_ORIGINS` (lista explícita por entorno).
  - `CORS_ALLOW_ORIGIN_REGEX` (por defecto patrón `*.vercel.app`).
- En `create_app`, `CORSMiddleware` se crea con:
  - `allow_origins=origins`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`.
- No se pasa `allow_origin_regex` al middleware en `create_app`.
- Tests de integración/e2e existentes validan:
  - origen permitido devuelve `access-control-allow-origin`.
  - origen no permitido no devuelve cabecera y responde `400/403`.

### 2.3 Trusted Host / cabeceras de seguridad

- `TrustedHostMiddleware` usa `settings.ALLOWED_HOSTS`.
- En producción, `config.py` predefine hosts permitidos (`app.ablogistics-os.com`, `api.ablogistics-os.com`, `*.vercel.app`, `*.railway.app`, etc.) y permite merge con env.
- Nginx añade en `443`:
  - `Strict-Transport-Security`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`.

### 2.4 Rate Limiting (Redis, tenant/IP, buckets)

- Backend usa `limits` Moving Window:
  - estrategia compartida con Redis cuando `REDIS_URL` existe.
  - fallback memoria en `TESTING=true` o `DEV_MODE=true` sin Redis.
  - en producción sin `REDIS_URL`, `get_rate_limit_strategy/get_rate_limit_storage_uri` elevan `RuntimeError`.
- Identidad de limitación (`resolve_rate_limit_identity`):
  - prioridad: `empresa_id` en JWT -> `usuario_id/sub` -> IP.
- Límites implementados:
  - `AuthLoginRateLimitMiddleware`: `10 per minute` por IP para `/auth/login` y `/auth/refresh`.
  - `GlobalIPRateLimitMiddleware`: `100 per minute` por IP para tráfico general.
  - `BIRateLimitMiddleware`: `30 per minute` por bucket BI.
  - `FiscalVerifactuRateLimitMiddleware`: `10 per minute` para envíos fiscales (rutas VeriFactu/finalizar/reenviar).
  - `TenantRateLimitMiddleware`: sliding window por tenant con RPM de plan y overrides (`TENANT_RATE_LIMIT_OVERRIDES`).
  - `EndpointCostRateLimitMiddleware`: buckets `ai/maps/ocr` con límites configurables (`AI_RATE_LIMIT`, `MAPS_RATE_LIMIT`, `OCR_RATE_LIMIT`).
- Exenciones definidas:
  - paths (`/live`, `/health`, `/ready`, docs/openapi, etc.) y prefijos de webhook/rutas.

### 2.5 OpenAPI (estado actual)

- `attach_custom_openapi()`:
  - añade `securitySchemes` (`HTTPBearer`, `BearerAuth`, `WebhookHMAC`).
  - añade schema `RateLimitError`.
  - inyecta respuesta `429` por operación.
- En app:
  - endpoint principal `/openapi.json`.
  - alias versionado `/api/v1/openapi.json` (compatibilidad histórica).
- Tests de integración verifican presencia de `BearerAuth` y respuestas `429`.

## 3) Núcleo Financiero y Fiscal

### 3.1 VeriFactu / AEAT / XAdES

- `verifactu_sender.py` implementa:
  - construcción de `RegistroAlta` (SuministroLR).
  - firma XAdES-BES enveloped (`sign_xml_xades` y ruta `crypto_service.sign_invoice_xml` con P12).
  - envoltorio SOAP 1.2 (`RegFactuSistemaFacturacion`).
  - envío mTLS con retries exponenciales y clasificación de errores.
- `aeat_soap_client.py` + `aeat_client_py/zeep_client.py`:
  - cliente Zeep/WSDL oficial AEAT.
  - parseo tipado de `RespuestaRegFactuSistemaFacturacion`.
  - soporte `SOAP Fault` y validación XSD opcional de payload.
- Endpoint de envío final:
  - `POST /api/v1/verifactu/submit-final/{factura_id}` en `backend/app/api/v1/verifactu.py`.

### 3.2 Hashing e inalterabilidad fiscal

- `backend/app/core/verifactu_hashing.py` declara:
  - `CanonicalHashService.generate_verifactu_hash` como punto canónico.
  - cadena SHA-256 sobre `NIF + Número/Serie + Fecha + Importe + HuellaAnterior`.
- `VerifactuService`:
  - resuelve eslabón previo por serie/empresa.
  - verifica cadena (`verificar_cadena_facturas`).
  - usa hash génesis por emisor (`get_verifactu_genesis_hash_for_issuer`).
- Auditoría de cadena expuesta por API:
  - `/api/v1/verifactu/verificar-cadena`
  - `/api/v1/verifactu/audit/verify-chain`
  - `/api/v1/verifactu/audit/chain-repair`

### 3.3 Motor matemático (Decimal y redondeo)

- `backend/app/core/math_engine.py`:
  - inicializa contexto global Decimal (`prec=28`, `ROUND_HALF_UP`, trap `FloatOperation`).
  - cuantización monetaria a `0.01` con `ROUND_HALF_UP`.
  - funciones de cálculo de factura (base/cuota/total) sobre `Decimal`.
  - validaciones de integridad de redondeo (`RoundingIntegrityError`).
  - cuantización ESG snapshot dedicada:
    - km: `0.001`
    - CO2 kg: `0.000001`

### 3.4 Snapshots ESG y bloqueo WORM operativo

- Migración `20260429120000_esg_period_snapshots_km_quality.sql`:
  - crea tabla `public.esg_period_snapshots`.
  - índice único por `empresa_id + period_year + period_month`.
  - columna `content_sha256` + `snapshot_payload`.
  - trigger `trg_esg_period_snapshots_immutable` bloquea `UPDATE/DELETE`.
  - añade en `portes`:
    - `esg_km_source`
    - `esg_data_locked`
  - trigger `trg_portes_block_esg_when_locked` bloquea cambios en CO2/distancia cuando `esg_data_locked=true`.
  - habilita RLS en snapshots con `public.app_current_empresa_id()`.

## 4) Tests y Resiliencia

### 4.1 Estado de suite y estructura

- `backend/pytest.ini`:
  - `testpaths = tests`
  - `asyncio_mode = auto`
- Conteo actual en `backend/tests`:
  - archivos con tests: `87`
  - funciones `test_*` detectadas: `390`

### 4.2 Cobertura (coverage) observable en repo

- Existe artefacto local `backend/.coverage`.
- No se detectan flags `--cov` ni job de cobertura en `.github/workflows/ci.yml` o `deploy.yml`.
- `python -m coverage report` sobre el artefacto local actual devuelve:
  - `app/services/finance_transactional_kpis.py`: `75%` (307 stmts, 78 miss)
  - `TOTAL`: `75%` (sobre ese conjunto registrado en el artefacto local).

### 4.3 _FakeDb mocks y aislamiento de red

- `backend/tests/conftest.py` define `_FakeQuery` y `_FakeSupabaseDb`.
- Se observan múltiples `_FakeDb`/`_Fake*` en tests unitarios/integración (`test_security_isolation`, `test_facturas_service_recalculate`, `test_portes_service`, etc.).
- `conftest.py` instala dobles para:
  - Stripe (`_install_stripe_test_double`)
  - WeasyPrint (`_install_weasyprint_test_double`)
  - Rapidfuzz (`_install_rapidfuzz_test_stub`)

### 4.4 E2E e integración con `create_app()`

- `backend/tests/integration/test_app_wiring.py` usa `TestClient(create_app())`.
- `backend/tests/integration/test_app_wiring_e2e.py` usa `ASGITransport` + `create_app()`.
- `backend/tests/integration/test_api_protection.py` valida rate limits y OpenAPI 429 en app de prueba con middlewares reales.

### 4.5 Guardarraíles CI/CD

- `ci.yml`:
  - job backend con Postgres 15 service.
  - guardrail explícito: prohíbe mutaciones directas sobre `audit_logs` (regex + fail).
  - instala dependencias WeasyPrint del sistema para tests.
- `deploy.yml`:
  - bloquea flujo si fallan pytest/backend, build+unit frontend, auditorías de dependencias.
  - ejecuta `pip-audit`, `npm audit --audit-level=critical`, Trivy y generación de SBOM (Syft).
  - pipeline de imagen GHCR condicionado a jobs previos.

## 5) Estado de IA (proveedores y fragmentación endpoints)

### 5.1 Proveedores y routing IA

- `advisor_service.py` usa LiteLLM (`litellm.acompletion`, `litellm.aembedding`).
- Cadena de modelos:
  - primario configurable (`ADVISOR_MODEL` / `ADVISOR_LLM_MODEL`, default `openai/gpt-4o`).
  - fallback configurable (default `anthropic/claude-3-5-sonnet-20240620`).
- Credenciales resueltas vía `get_secret_manager()`:
  - OpenAI, Anthropic, Azure OpenAI, Gemini.
- `openai_configured()` en advisor actúa como alias de disponibilidad multi-provider (`advisor_llm_configured()`).

### 5.2 Endpoints activos de LogisAdvisor y persistencia

- Endpoint canónico activo:
  - `POST /api/v1/advisor/ask` (`backend/app/api/v1/advisor.py`).
- Persistencia chat activa:
  - `POST /api/v1/advisor/sessions`
  - `GET /api/v1/advisor/sessions`
  - `GET /api/v1/advisor/sessions/{session_id}/messages`
  - servicio: `backend/app/services/chat_persistence_service.py` (tablas `chat_sessions`, `chat_messages`).
- Frontend usa `/api/v1/advisor/ask` en:
  - `frontend/src/components/chat/LogisAdvisor.tsx`
  - `frontend/src/lib/api.ts` (incluye streaming SSE para advisor).

### 5.3 Fragmentación `chatbot.py` vs `advisor.py` (estado de código)

- En `backend/app/api/v1` no existe actualmente ningún archivo `chat.py` ni `chatbot.py`.
- En `main.py` se incluye router `advisor_v1` en prefijo `/api/v1/advisor`.
- En el estado git de la sesión aparecen eliminados:
  - `backend/app/api/v1/chat.py`
  - `backend/app/api/v1/chatbot.py`

## 6) Observaciones factuales adicionales de configuración

- `config.py` exige `DATABASE_URL` explícita en `ENVIRONMENT=production` (lanza `ConfigError` si falta).
- `main.py` también vuelve a validar `DATABASE_URL` en producción antes de levantar app.
- `main.py` expone health:
  - `/live` (liveness, vía router de health)
  - `/health` (readiness con checks Supabase + Redis, devuelve `503` si dependencia crítica falla).
- En terminal de trabajo actual, CLI Supabase usada está en `v2.90.0` y muestra update disponible `v2.95.4`.

