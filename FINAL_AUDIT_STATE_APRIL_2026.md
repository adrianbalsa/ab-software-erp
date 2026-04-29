# Radiografía factual del repositorio — abril 2026

**Alcance:** estado del árbol de código y documentación versionada en el repositorio en la fecha de elaboración (sesión de auditoría técnica).  
**Método:** lectura de archivos, búsqueda estructurada y ejecución de `pytest` en `backend/`.  
**No incluye:** verificación de entornos desplegados fuera del git, credenciales, ni contenido de data room externa.

---

## 1. Estado de Due Diligence (documental)

| Hecho | Evidencia en repo |
|--------|---------------------|
| El checklist `DD_REMEDIATION_CHECKLIST.md` declara **progreso global 90%** en §0. | Líneas 19–20: `Estado global` y `Progreso global: 90%`. |
| **Fase 1** marcada **100%** y **cerrada** (§0). | Líneas 24–25. |
| **Fase 2** marcada **100%** y **cerrada** (§0). | Líneas 25–26. |
| **Fase 3** global **~90%**; texto: documentación lista; **pendiente** §3.4 archivo en data room y firma acta GO. | Líneas 26–27. |
| **§3.4** contiene ítems **sin marcar** (`[ ]`): evidencias §3.1 archivadas en data room (refs. `DD-2026-04-002`…`006`) y acta GO (`DD-2026-04-001`). | Líneas 130–135. |
| El **índice** `docs/dd/EVIDENCE_VAULT_INDEX.md` tiene columnas **Ubicación** y **Fecha archivo** con valor literal `_RELLENAR_` para las filas `DD-2026-04-001` … `DD-2026-04-006`. | Tabla en líneas 9–16 de ese archivo. |
| Runbook §3.4 referenciado: `docs/dd/RUNBOOK_3_4_DATA_ROOM_ARCHIVE.md` (citado en checklist §3.4). | `DD_REMEDIATION_CHECKLIST.md` líneas 130–132. |
| El log §5 del checklist registra un ajuste intermedio a **95%** y posteriormente **90%** con §3.4 pendiente. | Líneas 169–171 de `DD_REMEDIATION_CHECKLIST.md`. |

**Conclusión factual (solo sobre texto versionado):** el repositorio **documenta** Fases 1 y 2 como completadas al 100%, Fase 3 en ~90% con **3.3** marcada hecha en checklist y **3.4** explícitamente abierta; el índice de data room **no** muestra ubicaciones/fechas archivadas rellenas.

---

## 2. Salud del código y tests

| Hecho | Evidencia |
|--------|-----------|
| `pytest --collect-only -q` en `backend/` **colecciona 446 tests**. | Salida de `python -m pytest --collect-only -q` (446 tests collected). |
| `pytest -q --tb=no` en `backend/` **termina con 446 passed**, exit code 0, ~118 s en el entorno de ejecución de la auditoría. | Salida: `446 passed, 4 warnings in 118.08s`. |
| El archivo **`backend/tests/integration/test_app_wiring_e2e.py` existe** y define **3** pruebas: `test_cors_integrity_allowed_and_disallowed_origins`, `test_bi_rate_limit_applies_per_tenant_before_general`, `test_dependency_injection_uses_testing_false_in_e2e`. | Contenido del archivo (líneas 196–251). |
| Esas pruebas montan la app vía `create_app()`, transporte ASGI, cliente HTTP asíncrono; **Redis** se simula con `_FakeRedisClient` (pipeline ZSET); **no** hay `REDIS_URL` en el fixture (`monkeypatch.delenv("REDIS_URL", …)`). | `test_app_wiring_e2e.py` líneas 136–193, 224–238. |
| `test_bi_rate_limit_applies_per_tenant_before_general` espera **429** tras 31 peticiones GET a `/api/v1/bi/non-existing` y comprueba `bucket == "bi"` en el cuerpo JSON. | Mismo archivo líneas 226–238. |
| Carpeta **`backend/tests/e2e/`** contiene **5** módulos: `test_autonomous_onboarding_flow.py`, `test_banking_flow.py`, `test_banking_reconciliation_flow.py`, `test_onboarding_to_porte_flow.py`, `test_stripe_webhooks.py`. | `Glob` sobre `backend/tests/e2e/*.py`. |
| En esos módulos hay **al menos 7** funciones de test con nombre `test_*` (varias `async def`). | `rg '^async def test_|^def test_' backend/tests/e2e`. |
| `backend/pytest.ini` define `testpaths = tests`, marcador `rls_isolation`, `asyncio_mode = auto`. | Archivo `backend/pytest.ini`. |

**Discrepancia con cifra “430 tests”:** en la ejecución y recolección de esta auditoría el número **observado es 446**, no 430.

---

## 3. Cierre de red flags previos (verificación en código)

### 3.1 OpenAPI: `/docs`, `/redoc`, producción

| Hecho | Evidencia |
|--------|-----------|
| `FastAPI(...)` en `create_app()` fija **`docs_url="/docs"`**, **`redoc_url="/redoc"`**, **`openapi_url="/openapi.json"`** sin ramificar por `ENVIRONMENT`. | `backend/app/main.py` líneas 203–210. |
| `TenantRBACContextMiddleware` trata **`/docs`**, **`/redoc`**, **`/openapi.json`** como prefijos **públicos** (sin exigir el flujo de token → perfil para esas rutas). | `backend/app/middleware/tenant_rbac_context.py` líneas 17–24, 50–51. |
| En **`infrastructure/nginx/default.conf`** del repo, bajo 443, **`location /api/`** y rutas puntuales (`/health`, `/ready`, `/reports/`) van al upstream `backend`; **`location /`** va al **frontend**. No hay bloque `location` dedicado a `/docs` ni `/redoc` hacia el backend. | `default.conf` líneas 69–87. |

**Hecho compuesto:** el proceso FastAPI **expone** documentación interactiva en esas rutas; el middleware de tenant **no** las protege con JWT; el nginx de ejemplo **no** enruta `/docs` al backend en `location /`.

### 3.2 Pinning de dependencias de IA (`anthropic`, `google-genai`)

| Hecho | Evidencia |
|--------|-----------|
| En **`backend/requirements.txt`**, las líneas **`anthropic`** y **`google-genai`** aparecen **sin versión fija** (sin operador `==`). | Líneas 6 y 37 de `requirements.txt`. |
| Otras dependencias en el mismo archivo sí llevan pin explícito (p. ej. `openai==2.24.0`, `signxml==4.4.0`). | Mismo archivo. |

### 3.3 Rutas legacy de IA y endpoint Advisor

| Hecho | Evidencia |
|--------|-----------|
| El módulo **`backend/app/api/routes/advisor_legacy_deprecation.py`** define `POST /chat` y `POST /consult` bajo el router con **`HTTP 410 Gone`** y detalle JSON que incluye **`canonical_path`: `/api/v1/advisor/ask`**. | Archivo completo (líneas 22–29). |
| En `main.py`, ese router se monta con prefijo **`/ai`**. | `main.py` líneas 379–383. |
| El router v1 de advisor se monta en **`/api/v1/advisor`**. | `main.py` línea 462. |
| **`backend/app/api/v1/advisor.py`** documenta en docstring el endpoint canónico **`POST /api/v1/advisor/ask`** y la función `execute_advisor_ask` indica que las rutas legacy deben delegar ahí. | Líneas 4–5, 69–71. |
| En el estado git inicial de la sesión, **`backend/app/api/v1/chat.py`** y **`backend/app/api/v1/chatbot.py`** figuran como **eliminados** (`D` en `git status`). | Snapshot de `git status` proporcionado al inicio de la conversación. |
| Búsqueda de **`chat*.py`** bajo `backend/app/api/v1/`: **0 archivos** coincidentes en el workspace actual. | `Glob` `backend/app/api/v1/**/chat*.py`. |
| Existe **`backend/tests/api/v1/test_advisor_legacy_gone.py`** (citado en el checklist DD §2.1). | Presencia en repo (`git status` lo lista como no rastreado nuevo `??` en snapshot inicial; archivo presente en árbol). |

### 3.4 `SecretManagerService`

| Hecho | Evidencia |
|--------|-----------|
| Clase **`SecretManagerService`** y módulo **`backend/app/services/secret_manager_service.py`** existen; docstring describe backends **env**, **vault**, **aws**. | Primeras ~55 líneas del servicio. |
| Referencias a **`get_secret_manager`** / **`SecretManagerService`** en `backend/app/` aparecen en **múltiples** módulos (recuento de archivos con coincidencias: p. ej. `advisor_service`, `ai_service`, `stripe_service`, `ocr_service`, `encryption`, `alerts`, `worker`, webhooks, etc.). | `rg` sobre `backend/app` con patrones `get_secret_manager|SecretManagerService` (conteo por archivo en salida de herramienta). |

---

## 4. Núcleo fiscal y cumplimiento

### 4.1 VeriFactu y XAdES

| Hecho | Evidencia |
|--------|-----------|
| Dependencia **`signxml==4.4.0`** declarada en `requirements.txt`. | Línea 110. |
| Módulo **`backend/app/core/xades_signer.py`** usa **`signxml.xades.XAdESSigner`** y expone **`sign_xml_xades`**. | `rg` / lectura de imports en ese archivo. |
| **`backend/app/services/verifactu_sender.py`** importa y usa **`sign_xml_xades`**; comentarios de cabecera describen **XAdES-BES** enveloped del registro. | `rg` en `verifactu_sender.py`. |
| **`backend/app/services/crypto_service.py`** usa **`XAdESSigner`** de `signxml.xades`. | `rg` en ese archivo. |
| Tests que mencionan XAdES / firma: p. ej. `backend/tests/test_verifactu.py`, `backend/tests/unit/test_xades_signer.py`, `backend/tests/unit/test_verifactu_signature.py`. | `rg` "xades|sign_xml_xades" en `backend/tests`. |
| Módulo **`backend/app/core/verifactu_hashing.py`** existe en el árbol (referenciado en `git status` como modificado). | Estado del workspace. |

### 4.2 RLS (Postgres / Supabase)

| Hecho | Evidencia |
|--------|-----------|
| Migración **`supabase/migrations/20260319000009_rls_tenant_current_empresa.sql`** define **`public.app_current_empresa_id()`** y **`set_empresa_context`**, con comentario que alinea **`app.current_empresa_id`** con convención explícita. | Primeras ~45 líneas del archivo. |
| Múltiples migraciones bajo **`supabase/migrations/`** contienen términos **`RLS`**, **`ENABLE ROW LEVEL`**, o **`app_current_empresa_id`** (decenas de coincidencias en el conjunto de archivos `.sql`). | `rg` en `supabase/migrations/*.sql`. |
| Tests dedicados a aislamiento tenant/RLS en backend: p. ej. **`backend/tests/test_rls_tenant_isolation_dd.py`**, **`backend/tests/test_multi_tenant_rls.py`** (existencia en repo). | `Glob` / `git status`. |

### 4.3 Inmutabilidad snapshots ESG

| Hecho | Evidencia |
|--------|-----------|
| Migración **`supabase/migrations/20260429120000_esg_period_snapshots_km_quality.sql`** crea tabla **`public.esg_period_snapshots`**, función **`_esg_period_snapshots_immutable`**, trigger **antes de UPDATE o DELETE** que lanza excepción si la operación es UPDATE/DELETE. | Líneas 64–79 (y contexto de creación de tabla 37–62). |
| Existe **`backend/tests/unit/test_esg_worm_migration_contract.py`** (contrato WORM citado en DD §2.2). | Repo / checklist. |

### 4.4 Métricas BI y coherencia

| Hecho | Evidencia |
|--------|-----------|
| Módulo **`backend/app/core/bi_financial_health_contract.py`** documenta contrato para **`GET /api/v1/bi/financial-health`** y función **`financial_health_coherence_issues`**. | Primeras ~35 líneas. |
| Test **`backend/tests/unit/test_bi_financial_health_coherence.py`** presente en el árbol. | `git status` / listado de tests. |
| Router BI montado en `main.py` con prefijos bajo **`/api/v1`** (tags Business Intelligence). | `main.py` línea 463. |

---

## 5. Metadatos de la extracción

| Campo | Valor |
|--------|--------|
| Comando de recuento/ejecución de tests | `cd backend && python -m pytest --collect-only -q` y `python -m pytest -q --tb=no` |
| Resultado tests | **446** recogidos, **446** passed (4 warnings de dependencias/Sentry en el log de ejecución) |
| Fecha calendario usada en contexto de sesión | 2026-04-30 (metadata de entorno de usuario) |

---

*Fin del documento. Toda afirmación anterior está anclada a rutas de archivo o salida de comando reproducible en el clon auditado.*
