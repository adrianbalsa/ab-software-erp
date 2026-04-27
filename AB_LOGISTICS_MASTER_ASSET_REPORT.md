# AB Logistics OS — Master Asset Report (IP & Business Viability)

**Rol:** radiografía de propiedad intelectual y viabilidad técnica para due diligence.  
**Método:** revisión estática del repositorio (`/backend`, `/frontend`, `/infra`, `supabase/migrations`, workflows GitHub, configuración). **No se asume producción desplegada**; lo que no aparece en código o migraciones se marca explícitamente.  
**Fecha de corte del árbol:** abril 2026.

---

## 1. Estado de los 7 bloqueadores GTM

Cada ítem se clasifica según **evidencia en código**, no según intención documental.

| # | Bloqueador | Clasificación | Evidencia y matices |
|---|------------|---------------|---------------------|
| 1 | **Seudonimización RGPD** | **[VULNERABLE]** | Existe cifrado reversible de PII vía Fernet (`app/core/crypto.py` → `app/core/security.py`: `fernet_encrypt_string` / `fernet_decrypt_string`), consumido como `pii_crypto` en servicios fiscales y facturación. Eso es **cifrado de aplicación**, no un sistema de **seudónimos sustitutivos** (tokens estables desacoplados del titular) en pipelines analíticos, logs agregados o exportaciones. No hay capa unificada de “data subject pseudonym” transversal. Para un auditor RGPD estricto (Art. 4(5) + minimización), el riesgo es **interpretación**: cumple confidencialidad en campos cifrados; **no demuestra** seudonimización operativa end-to-end. |
| 2 | **Génesis Hash (VeriFactu)** | **[COMPLIANT]** | `get_verifactu_genesis_hash_for_issuer` (`verifactu_genesis.py`) resuelve hash génesis **por emisor** desde Secret Manager (`VERIFACTU_GENESIS_HASHES`); falla en runtime si falta (`verifactu_genesis_hash_missing_for_issuer`). El encadenamiento de emisión usa génesis + último hash persistido (`facturas_service.py`, lecturas SQL de cadena). |
| 3 | **S3 región / cifrado** | **[COMPLIANT]** | Flujos **backup** en `.github/workflows/backup_daily.yml`, `backup_restore_smoke.yml` e `infra/backup_system.sh`: comprobación de bucket en **EU (`eu-*`)**, upload con **SSE-S3 o SSE-KMS** (`BACKUP_S3_KMS_KEY_ID` / `AWS_S3_KMS_KEY_ID`), verificación `head-object` de `ServerSideEncryption`. **Matiz:** el producto principal de ficheros suele ser **Supabase Storage**, no buckets S3 propios de la app; la garantía S3 documentada aplica al **camino de backup**, no a todo el almacenamiento del tenant salvo que esté cableado igual en despliegue. |
| 4 | **Rate limiting por tenant** | **[COMPLIANT]** | `TenantRateLimitMiddleware` (`middleware/rate_limit_middleware.py`) + `resolve_rate_limit_identity` / `rate_limit_key` (`core/rate_limit.py`): claves por **JWT → `empresa_id`**, fallback IP. Overrides por tenant: `TENANT_RATE_LIMIT_DEFAULT`, `TENANT_RATE_LIMIT_OVERRIDES` (JSON) en `config.py`. Backend Redis compartido vía `limits` + `REDIS_URL`. **Deuda:** en errores de Redis/strategy algunos middlewares **dejan pasar** (`_log.warning` + continue) — riesgo operativo bajo ataque o Redis caído (fail-open). |
| 5 | **Caché de Maps (Redis)** | **[VULNERABLE]** | **Geocodificación:** Redis opcional (`geo_service.py`: `scanner:geo:v1:geocode:*`, TTL, métricas `hincrby`). **Rutas (Routes API v2):** persistencia principal en tabla **`geo_cache`** (Postgres) + caché en memoria por proceso (`_mem_route`); **no** hay clave Redis dedicada para el payload de ruta completo como en geocode. **`MapsService`** añade RAM + tabla `maps_distance_cache` para Distance Matrix. En multi-réplica, la coherencia de RAM es **por worker**, no compartida. Para el criterio literal “Maps cache = Redis”, el cumplimiento es **parcial**. |
| 6 | **Idempotencia de webhooks** | **[COMPLIANT]** | `claim_webhook_event` (`webhook_idempotency.py`): insert atómico en `webhook_events` con deduplicación por `(provider, external_event_id)` (detección `23505` / duplicate key). **Stripe:** `stripe_service.handle_webhook` → claim antes de procesar, `finalize_stripe_webhook_claim` / `release_stripe_webhook_claim` en éxito/error. **GoCardless:** `gocardless.py` usa el mismo patrón. Tests: `test_webhooks_gocardless_fulfilled.py`, e2e Stripe. |
| 7 | **Criptografía contraseñas (Argon2id)** | **[COMPLIANT]** | `hash_password_argon2id` / `PasswordHasher(..., type=Type.ID)` en `security.py`. **Residual controlado:** verificación contra **SHA-256 hex legacy** + migración lazy a Argon2 en login (`auth_service.py`). Migración Supabase `20260426225500_password_must_reset_legacy_sha256.sql` fuerza política de rotación. Riesgo residual solo mientras existan cuentas sin migrar — el diseño actual es **estándar de industria** con puente documentado. |

**Síntesis GTM:** dos ítems en **[VULNERABLE]** (seudonimización interpretada de forma estricta; caché Maps/Redis incompleta para rutas). El resto **[COMPLIANT]** con matices operativos (fail-open rate limit, S3 centrado en backup).

---

## 2. Análisis de propiedad intelectual (IP)

### 2.1 Math Engine (complejidad y rutas)

- **Ubicación:** `backend/app/core/math_engine.py` (+ reexport en `fiscal_logic.py`).
- **Redondeos:** `Decimal` con contexto `prec=28`, **`ROUND_HALF_EVEN`** (IEEE 754 / contable), cuantía **`0.01` EUR** (`FIAT_QUANT`), funciones `round_fiat`, `quantize_currency`, `to_decimal` (rechazo de NaN/inf, floats vía `Decimal(str(value))`).
- **Dominio no monetario:** `quantize_operational_km` a **milésimas de km** (`KM_OPERATIONAL_QUANT`); `aggregate_portes_km_bultos` evita `float(sum(...))` en agregados.
- **Rutas y costes:** `MathEngine.calculate_route_costs` (consumido en `routes_optimizer.py`) combina distancia, peajes y estimaciones de combustible para UI; los **km de API de mapas** llegan como `float` en la capa HTTP y se redondean para presentación (`round(km, 2)`), mientras el núcleo fiscal de facturas permanece en Decimal.
- **Deuda técnica:** `presupuestos_service.py` sigue un modelo **float-first** para presupuestos de obra (subtotales, IVA, total); no pasa por el mismo rigor que facturación VeriFactu. Es **inconsistencia de modelo numérico** entre módulos.

**Valor IP:** medio-alto en **facturación y cumplimiento**; medio en **presupuestos** por la rama float.

### 2.2 Módulo VeriFactu (XAdES-BES, encadenamiento, dificultad de réplica)

- **Huellas y encadenamiento preventivo:** `verifactu_hashing.py` centraliza SHA-256 para `VerifactuCadena.HUELLA_EMISION` y `HUELLA_FINGERPRINT`; importes canónicos vía `fiscal_amount_string_two_decimals` (dos decimales, half-even). El **hash anterior** debe ser no vacío; la primera factura usa **génesis** por emisor (Secret Manager), no cero mágico en código.
- **Firma XAdES-BES:** `xades_signer.py` — `signxml.xades.XAdESSigner`, **enveloped**, RSA-SHA256, digest SHA256, raíz esperada `RegistroAlta`. Duplicidad menor: `crypto_service.py` también envuelve `XAdESSigner` (convivencia / rutas legacy).
- **Envío AEAT:** `verifactu_sender.py` — SOAP 1.2, mTLS, validación XSD opcional, colas ARQ, códigos de error no reintentables (`XADES`, etc.). XML de registro en `suministro_lr_xml.py` / `aeat_xml_service.py`.
- **Pruebas:** `test_verifactu_signature.py`, `test_xades_signer.py`, tests de rectificativas y dead jobs.

**Dificultad de réplica desde cero:** **muy alta**. No es “un hash SHA”; integra normativa AEAT, XSD, perfil XAdES, gestión de certificados, mTLS, reconexión de cadena, génesis por emisor, colas y estados. Un competidor necesitaría **6–12+ meses** con equipo fiscal y de seguridad, más homologación con entorno AEAT.

### 2.3 Truck API y gestión de flotas (madurez)

- **No existe** un paquete literal `truck_api`. El equivalente funcional es: **portes** (`portes_service.py`, rutas `api/routes/portes.py`), **optimización de ruta** (`api/v1/routes_optimizer.py` + `MapsService.get_truck_route`), **flota** (`flota_ubicacion.py`, `flota_service`, tabla `flota` / mantenimiento en migraciones).
- **Madurez:** RBAC explícito en ubicación GPS (conductor solo su vehículo; owner/traffic_manager amplios). Live tracking y parches de coordenadas están **acotados por tenant** vía dependencias estándar.
- **Límites:** `optimize_route` documenta “Distance Matrix” pero el flujo principal usa **`get_truck_route`** (Routes); ordenación multi-ruta es **básica** (principal + opcional con waypoints; errores en waypoints se **tragan** con `except Exception: pass` — **pérdida silenciosa de calidad de servicio**). La IP de “optimizador combinatorio” tipo VRP **no** está; es **enrutamiento + CO₂ + costes** apoyado en Google.

**Valor IP:** alto en **integración mapas + coste + ESG**; bajo/medio en **optimización combinatoria avanzada** frente a TMS maduros.

---

## 3. Eficiencia operativa y unit economics

### 3.1 Llamadas a APIs de terceros (muestra verificada en código)

| Proveedor | Uso principal | Archivos / notas |
|-----------|---------------|-------------------|
| **Google Maps** | Distance Matrix, Routes API v2, Geocoding | `maps_service.py`, `geo_service.py` |
| **OpenAI / LiteLLM** | OCR visión, embeddings, modelos configurables | `ocr_service.py`, variables `OPENAI_*`, LiteLLM |
| **Google Gemini** | Alternativa OCR / visión | `ocr_service.py` |
| **Anthropic** | Chat / asistente según ruta | `api/v1/chatbot.py` |
| **Stripe** | Checkout, portal, webhooks, suscripciones | `stripe_service.py`, `api/v1/webhooks/stripe.py` |
| **GoCardless** | Open banking / pagos, webhooks | `payment_service.py`, webhooks GoCardless |
| **Resend / SMTP** | Email facturas / estrategia configurable | `email_service`, `facturas.py` (comentarios Resend) |
| **Sentry** | Telemetría opcional | `math_engine`, varios servicios |
| **AEAT** | SOAP VeriFactu (no “API REST” trivial) | `verifactu_sender.py` |

### 3.2 Mecanismos de ahorro (caché, batch, cuotas)

- **Caché:** Maps/geocode (Redis + Postgres + RAM); rutas (Postgres `geo_cache` + RAM); cuotas de uso por tenant (`usage_quota_service.py`, `CostMeter.MAPS`).
- **Batch:** `GeoBatchCache` reduce llamadas repetidas dentro de una misma operación de negocio.
- **OCR:** Selección de modelo con fallback; tests mockean red.
- **Huecos:** sin caché Redis unificada para **todas** las variantes de ruta; presupuestos sin deduplicación de coste LLM; **fail-open** en rate limit puede inflar coste bajo incidentes.

### 3.3 Base de datos Supabase (RLS, índices, triggers) y escala

- **RLS:** numerosas migraciones con `CREATE POLICY` / endurecimiento multi-tenant (`rls_jwt_strict_multi_tenant`, `rbac`, portal cliente, webhooks, bank sync). El workflow `backup_restore_smoke.yml` valida RLS tras restore (señal de madurez operativa).
- **Índices:** dispersos en migraciones (geo_cache, embeddings ivfflat, verifactu, webhooks, finance, flota). Hay consolidación masiva en `20260415133000_pending_migrations_consolidated.sql` (alto impacto en revisiones — conviene tratarlo como **punto de control** en auditorías de migración).
- **Triggers:** auditoría append-only, huella cadena, procesos batch (p. ej. `audit_logs_triggers`, `audit_trail_process_audit_log`).
- **Escala “miles de registros por cliente”:** Postgres con RLS escala bien si las políticas usan **índices alineados con `empresa_id`** en consultas calientes; el repo incluye vistas como `portes_activos_math_engine_view` y patrones de soft delete. **Riesgo:** tablas de caché/geo y embeddings crecen con uso; requieren **TTL, vacuum y políticas de retención** monitorizadas (TTL en código para Redis geo; Postgres depende de upserts y columnas de expiración donde existan).

---

## 4. Preparación para escala internacional

- **Patrón `FiscalProvider`:** **no existe** en el código (búsqueda literal sin matches). La lógica fiscal está **acoplada al dominio español / AEAT**: `fiscal_logic`, `verifactu_*`, `aeat_*`, IVA, NIF.
- **Inyectar Suiza o Portugal:** no es un “plugin” de interfaz; sería **fork conceptual** de capa fiscal (nuevos esquemas, proveedor tributario, posiblemente otro formato de firma o reporting), manteniendo portes/flota como dominio logístico reutilizable.
- **Conclusión:** el **core logístico** es reutilizable internacionalmente; el **núcleo fiscal actual** es **bajo acoplamiento interno** (módulos separados) pero **alto acoplamiento país** (España). Esfuerzo estimado para un segundo país fiscal: **grande** (meses), no semanas.

---

## 5. Documentación y mantenibilidad (handover)

### 5.1 README y entrada al repo

- **No hay `README.md` en la raíz** del monorepo (solo fragmentos: `frontend/README.md`, `landing/README.md`, `infra/terraform/README.md`, `README_SECURITY.md`, etc.). Un equipo nuevo **pierde el hilo** del arranque sin un índice raíz.
- **Documentación dispersa pero rica:** `docs/operations/*`, `docs/INFRASTRUCTURE.md`, `AB_LOGISTICS_DUE_DILIGENCE_BASE.md`, `.env.example`, `production.env.example`.

### 5.2 Legibilidad del código

- **Fortalezas:** tipado Pydantic, servicios por dominio, tests de seguridad/rate limit/VeriFactu, comentarios en español en zonas fiscales críticas.
- **Debilidades:** algunos `except Exception: pass` en flujos de producto (waypoints en rutas), dualidad float/Decimal entre módulos, consolidación grande de SQL en una migración, configuración muy ramificada (`config.py`).

### 5.3 ¿Handover en menos de una semana?

- **Operar** el sistema (despliegue, variables, backups): **sí**, con la documentación existente y acceso a secretos.
- **Asumir responsabilidad total** (cambios fiscales, certificados AEAT, tuning RLS, incidentes VeriFactu): **no razonable en &lt; 1 semana** para un equipo medianamente grande sin transferencia explícita; el **conocimiento fiscal y de colas** es el cuello de botella, no el framework.

---

## 6. Tabla ejecutiva de riesgos IP / negocio

| Área | Riesgo | Severidad |
|------|--------|-----------|
| RGPD “seudonimización” vs cifrado puntual | Expectativas regulatorias mal alineadas con implementación | Media |
| Caché Maps multi-réplica | RAM por worker; coste Google puede dispararse | Media |
| Rate limit fail-open | Disponibilidad priorizada sobre abuso | Media-Baja |
| Fiscal multi-país | Reimplementación, no configuración | Alta (si roadmap internacional) |
| Ausencia README raíz | Onboarding lento, errores de setup | Baja-Media |

---

**Disclaimer:** Este informe refleja el estado del **código y migraciones versionadas**. Variables de entorno, secretos, buckets reales y configuración de Supabase/Vercel/AWS en producción deben contrastarse en **auditoría de despliegue** aparte.
