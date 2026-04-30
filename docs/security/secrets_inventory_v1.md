# Secrets Inventory v1 (DD Phase 1)

Fecha: `2026-04-29`  
Owner: `Adrian (solo-founder)`  
Objetivo: inventariar secretos criticos y detectar accesos directos fuera del flujo central `SecretManagerService`.

## 1) Secretos criticos identificados

### Identidad y autenticacion

- `JWT_SECRET_KEY` / `JWT_SECRET`
- `SUPABASE_SERVICE_KEY` / `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET` (si aplica validacion local HS256)

### Pagos y banking

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `GOCARDLESS_SECRET_ID`
- `GOCARDLESS_SECRET_KEY`
- `GOCARDLESS_ACCESS_TOKEN`
- `GOCARDLESS_WEBHOOK_SECRET`

### IA y OCR

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY` / `GOOGLE_API_KEY`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OCR_*` (si se habilita OCR Azure en entorno)

### Fiscal / certificados

- `AEAT_CERT_PASSPHRASE`
- `AEAT_CLIENT_P12_PASSWORD`
- `AEAT_CERT_PFX` (material sensible, aunque no API key)

### Cifrado app

- `FERNET_KEY`

---

## 2) Hallazgos de acceso directo (`os.getenv`) - resumen

Alcance escaneado: `backend/` (codigo app + scripts + tests).

### A) Riesgo alto (servicios de aplicacion, potencialmente secretos)

- `backend/app/services/reconciliation_service.py`
  - usa `OPENAI_MODEL` por `os.getenv` y reporta mensajes sobre `OPENAI_API_KEY`.
  - accion: enrutar configuracion y disponibilidad via `SecretManagerService` + helper central.

- `backend/app/services/ocr_service.py`
  - usa `OCR_*` / `LITELLM_*` por `os.getenv`.
  - accion: separar `model config` (no secreto) de `api keys` (secreto) y forzar secreto central.

- `backend/app/services/advisor_service.py`
  - usa `ADVISOR_*`, `OPENAI_MODEL`, `LITELLM_*` por `os.getenv`.
  - accion: centralizar lectura de configuracion sensible/no sensible en modulo unico.

- `backend/app/worker.py`
  - usa `AEAT_CERT_PFX` por `os.getenv`.
  - accion: obtener material sensible desde secret manager/backend seguro.

### B) Riesgo medio (config no secreta, pero dispersa)

- `backend/app/services/bi_service.py`, `esg_service.py`, `eco_service.py`, `report_service.py`
  - usan `os.getenv` para factores y parametros operativos.
  - accion: migrar a `settings` central para trazabilidad y validacion.

- `backend/app/core/*` (`alerts.py`, `health_checks.py`, `logging_config.py`, `redis_config.py`)
  - mayormente configuracion operativa.
  - accion: mantener permitido si no son secretos; documentar explicitamente.

### C) Fuera de alcance de riesgo P1 inmediato

- `backend/tests/*` y `backend/scripts/*`
  - uso de `os.getenv` esperado para pruebas y utilidades.
  - accion: no bloqueante para DD P1, revisar despues de cierre de ruta critica.

---

## 3) Lista priorizada de remediacion (P1)

1. Bloquear nuevos accesos directos a secretos en `backend/app/**` (guardrail CI).
2. Remediar `reconciliation_service.py`, `ocr_service.py`, `advisor_service.py`, `worker.py`.
3. Documentar excepciones permitidas (solo config no secreta) en `backend/app/core/**`.
4. Añadir test de regresion: "secreto critico nunca se lee directo con os.getenv en servicios".

---

## 4) Evidencia tecnica de esta revision

- Comando de descubrimiento principal: `rg "os\\.getenv\\(" backend/`
- Correlacion por secretos criticos: `rg "(OPENAI_API_KEY|...|SUPABASE_SERVICE_KEY)" backend/`
- Checklist relacionada: `DD_REMEDIATION_CHECKLIST.md` item `1.1 Inventario completo de secretos criticos`

## 5) Remediacion aplicada (2026-04-29)

- `backend/app/worker.py`
  - `AEAT_CERT_PFX` ahora via `get_secret_manager().get_aeat_cert_pfx()`.
- `backend/app/services/alert_service.py`
  - webhook alertas ahora via `get_secret_manager().get_alert_webhook_url()`.
- `backend/app/core/alerts.py`
  - `ALERT_WEBHOOK_URL` resuelto por `SecretManagerService`.
- `backend/app/core/mtls_certificates.py`
  - webhook de expiracion mTLS ahora via `get_secret_manager().get_mtls_cert_expiry_alert_webhook_url()`.
- `backend/app/services/secret_manager_service.py`
  - nuevos getters tipados: `get_alert_webhook_url`, `get_mtls_cert_expiry_alert_webhook_url`, `get_aeat_cert_pfx`.

Validacion:
- `rg` de secretos criticos con `os.getenv` sobre `backend/app` -> `No matches found`.
- Tests ejecutados: `pytest backend/tests/unit/test_vault_kv_secret_manager.py backend/tests/unit/test_aws_secrets_manager_backend.py -q` -> `11 passed`.

