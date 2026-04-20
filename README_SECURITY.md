# Seguridad: gestión de secretos y rotación

Este documento cubre el **Hallazgo 115** (secretos estáticos sin rotación) y el uso del
`SecretManagerService` como interfaz única hacia un gestor profesional (Railway Secrets hoy;
HashiCorp Vault / AWS Secrets Manager preparados vía `SECRET_MANAGER_BACKEND`).

Contratos HTTP, Postgres/cola y límites de acoplamiento con proveedores: `docs/PLATFORM_CONTRACTS.md`.

## Divulgación coordinada (RFC 9116)

| Variable | Uso |
|----------|-----|
| `SECURITY_CONTACT_EMAIL` | Dirección publicada en `/.well-known/security.txt` y en `GET /api/v1/public/compliance` (`security_contact_email`). Debe ser un **buzón real**, con **MX/DKIM** en el dominio público y **monitorización** (alertas a equipo de plataforma). Valor canónico del proyecto: `security@ablogistics-os.com`. |

En **Railway** / **Terraform** del repo, la variable se inyecta por defecto vía `infra/terraform` (`security_contact_email`). En **Docker Compose**, el valor por defecto del servicio backend es el mismo si no defines la variable en `.env`.

## Estado de cierre (Due Diligence #115)

**Cierre formal declarado:** 2026-04-19. El hallazgo queda resuelto a nivel de **código y
documentación** con: inventario de variables críticas, lectura centralizada
(`backend/app/services/secret_manager_service.py`), backends Vault y AWS, rotación operativa
descrita, y tests unitarios con mocks (sin sustituir una validación operativa en el entorno del
cliente: políticas Vault/IAM y un smoke de lectura en staging siguen siendo responsabilidad de
despliegue).

## Secretos críticos inventariados

| Variable | Uso |
|----------|-----|
| `STRIPE_SECRET_KEY` | API de Stripe (Checkout, Portal, webhooks firmados vía `STRIPE_WEBHOOK_SECRET`) |
| `GOCARDLESS_ACCESS_TOKEN` | SDK GoCardless Pro (pagos) |
| `GOCARDLESS_SECRET_ID` / `GOCARDLESS_SECRET_KEY` | Bank Account Data (token HTTP) |
| `GOCARDLESS_WEBHOOK_SECRET` | Verificación HMAC de webhooks |
| `ENCRYPTION_KEY` / `PII_ENCRYPTION_KEY` / `FERNET_PII_KEY` | Cifrado Fernet PII en reposo |
| `ENCRYPTION_KEY_PREVIOUS` / `PII_ENCRYPTION_KEY_PREVIOUS` / `FERNET_PII_KEY_PREVIOUS` | Descifrado durante rotación (multi-key) |
| `JWT_SECRET_KEY` o `JWT_SECRET` | Firma de JWT HS256 (`/auth/login`) |
| `OPENAI_API_KEY` | OpenAI (LogisAdvisor herramientas, conciliación IA, etc.) |
| `ANTHROPIC_API_KEY` / `CLAUDE_API_KEY` | Anthropic (endpoint chat legacy `/chatbot/ask`) |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google AI / Gemini (LiteLLM / asistente) |
| `AZURE_API_KEY` / `AZURE_OPENAI_API_KEY` | Azure OpenAI (LiteLLM) |
| `AZURE_ENDPOINT` / `AZURE_KEY` | Azure Document Intelligence (OCR de facturas/gastos) |

Lectura en código: ``get_secret_manager()`` (`backend/app/services/secret_manager_service.py`) — **no** usar ``os.getenv`` para estas claves en servicios de aplicación.

## Master Key y Vault

En despliegues con **HashiCorp Vault** o **AWS Secrets Manager**, el runtime no almacena los
secretos de aplicación en el disco del contenedor: un **master key** o **auth method**
(IAM role, AppRole, Kubernetes SA JWT, etc.) permite al proceso **leer** secretos en caliente.

- **Railway / Docker actuales:** los valores se inyectan como variables de entorno; el “master”
  es el control de acceso al proyecto Railway (quién puede ver variables) más el cifrado en
  tránsito de la plataforma.
- **Vault (KV v2, implementado):** con `SECRET_MANAGER_BACKEND=vault`, `VAULT_ADDR`, `VAULT_KV_PATH`
  (sin prefijo `data/`) y auth según `VAULT_AUTH_METHOD`:
  - **`token`** (default): `VAULT_TOKEN` o `VAULT_TOKEN_FILE`.
  - **`kubernetes`**: `VAULT_K8S_ROLE` y JWT del pod (`VAULT_K8S_JWT_PATH`, por defecto la ruta
    estándar del ServiceAccount).
  - **`approle`**: `VAULT_APPROLE_ROLE_ID` y `VAULT_APPROLE_SECRET_ID` o `VAULT_APPROLE_SECRET_ID_FILE`.
  El mapa `data` del secreto KV replica el inventario de variables. Caché TTL
  (`VAULT_CACHE_TTL_SECONDS`, default 120 s); `bump_integration_secret_version()` fuerza re-read;
  ante **403** se re-autentica y se reintenta una vez. Opcionales: `VAULT_KV_MOUNT` (default `secret`),
  `VAULT_NAMESPACE`, `VAULT_CA_CERT`, `VAULT_TLS_VERIFY`, `VAULT_HTTP_TIMEOUT_SECONDS`.
- **AWS Secrets Manager:** `SECRET_MANAGER_BACKEND=aws` o `secretsmanager` y
  `AWS_SECRETS_MANAGER_SECRET_ID` (nombre o ARN). El `SecretString` debe ser **JSON** con las
  mismas claves que el inventario. Región: `AWS_REGION` o `AWS_DEFAULT_REGION` (opcional; cadena
  de credenciales IAM/IRSA/ECS). Caché: `AWS_SECRETS_CACHE_TTL_SECONDS` (default 120). Sin ID de
  secreto, la app vuelve a leer solo desde entorno.
- **Vault sin API (solo inyección):** si la configuración Vault no está completa, se usa
  `SaaSEnvSecretProvider` (secretos solo por entorno) y un aviso único en log.
- **Nunca** commitear claves; rotar tras baja de personal con acceso al panel de secretos.

## Rotación operativa

1. Ejecutar el asistente (solo metadatos en auditoría; **no** imprime secretos existentes):

   ```bash
   python scripts/rotate_secrets.py --kind pii --dry-run
   ```

2. Actualizar el gestor (Railway variables, Vault path, etc.) según las instrucciones del script.

3. **PII / Fernet:** poner la clave antigua en `ENCRYPTION_KEY_PREVIOUS` (o `PII_ENCRYPTION_KEY_PREVIOUS`)
   y la nueva en `ENCRYPTION_KEY` (o `PII_ENCRYPTION_KEY`). El backend descifra con la primaria y,
   si falla, prueba las anteriores (`app.core.encryption`, `app.core.security`).

4. **Stripe / GoCardless:** las rutas de negocio re-aplican `stripe.api_key` y reconstruyen el
   cliente GoCardless cuando sube el contador interno (`bump_integration_secret_version`) o,
   de forma habitual, **tras reiniciar** el worker tras cambiar el entorno.

5. Auditoría `SECURITY_SECRET_ROTATION`: el middleware HTTP puede registrar eventos encolados con
   `queue_security_secret_rotation_audit`; el script CLI usa la misma RPC si define
   `SECURITY_AUDIT_EMPRESA_ID` y credenciales Supabase service role.

## Tests

`SECRET_MANAGER_BACKEND=mock` equivale hoy a lectura desde entorno (sin red externa). Tras
`monkeypatch` de variables, llamar a `reset_secret_manager()` (ya hecho en `conftest`) para
limpiar el singleton. Mocks: `tests/unit/test_vault_kv_secret_manager.py` (Vault),
`tests/unit/test_aws_secrets_manager_backend.py` (AWS).
