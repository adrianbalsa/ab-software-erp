# Despliegue SaaS: Railway (API) + Vercel (frontend) + Supabase

Contratos de API, cola y portabilidad de datos: `docs/PLATFORM_CONTRACTS.md`.

## 1. Backend (Railway)

### Directorio raíz del servicio

En **Railway → Service → Settings → Root Directory**, usa `backend` (donde están `requirements.txt`, `app/` y `Procfile`).

### Comando de arranque

- **`Procfile`**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **`railway.json`**: mismo comando en `deploy.startCommand`.

Railway inyecta `$PORT` automáticamente.

### CORS (FastAPI)

- **`CORS_ALLOW_ORIGINS`**: lista separada por comas con tu frontend en producción, por ejemplo:
  - `https://www.tudominio.com,https://tudominio.com`
- Por defecto se permite también el patrón **`https://*.vercel.app`** vía `allow_origin_regex` (previews de Vercel).
- Para desactivar solo el regex de Vercel: `CORS_ALLOW_ORIGIN_REGEX=0` o vacío.
- Para un regex personalizado: `CORS_ALLOW_ORIGIN_REGEX=^https://.*\.tudominio\.com$`

---

## 2. Variables de entorno — Railway (backend)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `SUPABASE_URL` | Sí | URL del proyecto Supabase (`https://xxx.supabase.co`). |
| `SUPABASE_KEY` | Sí | Clave **anon** o **service** según cómo llame el backend (RLS). |
| `SUPABASE_SERVICE_KEY` | No | Si usas operaciones con service role; por defecto se reutiliza `SUPABASE_KEY`. |
| `JWT_SECRET_KEY` o `JWT_SECRET` | Sí | Secreto para firmar tokens de login propios (`/auth/login`). Debe ser fuerte y único en producción. |
| `SUPABASE_JWT_SECRET` | Recomendado | Secreto JWT del panel Supabase (**Settings → API → JWT Secret**), para validar tokens de Supabase Auth si aplica. Si no se define, se usa `JWT_SECRET_KEY`. |
| `SUPABASE_JWT_ISSUER` | No | Override del `iss` del JWT (dominio custom de Auth). |
| `JWT_ALGORITHM` | No | Por defecto `HS256`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Por defecto `60`. |
| `CORS_ALLOW_ORIGINS` | Sí (prod) | Orígenes del frontend, p. ej. `https://www.tudominio.com,https://tudominio.com`. |
| `CORS_ALLOW_ORIGIN_REGEX` | No | Por defecto: previews `*.vercel.app`. `0` o vacío = desactivar. |
| `OPENAI_API_KEY` | Condicional (OCR / IA) | OCR de tickets de combustible y asistentes: el backend usa **LiteLLM** con visión (`openai/gpt-4o` por defecto si hay clave). Ver `backend/app/services/ocr_service.py`. |
| `GEMINI_API_KEY` o `GOOGLE_API_KEY` | Condicional (OCR / IA) | Alternativa **Gemini** para el mismo OCR si no hay `OPENAI_API_KEY`. |
| `OCR_VISION_MODEL` | No | Override del modelo LiteLLM para tickets (p. ej. `openai/gpt-4o`, `gemini/gemini-1.5-flash`). |
| `OCR_GEMINI_MODEL` | No | Modelo Gemini cuando se elige esa ruta (por defecto `gemini/gemini-1.5-flash`). |
| `LITELLM_MODEL_OCR` | No | Modelo LiteLLM para **Vampire Radar** (documentos en `ai_documents`). |
| `LITELLM_EMBEDDING_MODEL` | No | Embeddings post-OCR en Vampire Radar (por defecto `openai/text-embedding-3-small`). |
| `PROJECT_NAME` | No | Nombre en OpenAPI. |
| `VERIFACTU_SERIE_FACTURA` | No | Serie de numeración (por defecto `FAC` en código). |

> Ya **no** se usa Azure Document Intelligence para OCR; las claves `AZURE_ENDPOINT` / `AZURE_KEY` son obsoletas para este producto.

---

## 3. Variables de entorno — Vercel (frontend)

Configura **al menos una** de estas (la app acepta ambas; prioridad: `NEXT_PUBLIC_API_URL`):

| Variable | Ejemplo |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | `https://api.tudominio.com` |
| `NEXT_PUBLIC_API_BASE_URL` | Mismo valor (alias retrocompatible) |

Debe ser la URL **pública** del backend en Railway (o tu subdominio `api.*`).

---

## 4. DNS: dominio propio

Sustituye `tudominio.com` por tu dominio real.

### `www` → Vercel

1. En **Vercel → Project → Settings → Domains**, añade `www.tudominio.com` y `tudominio.com` (Vercel indica los registros exactos).
2. En tu proveedor DNS suele ser:
   - **CNAME** `www` → `cname.vercel-dns.com` (o el valor que muestre Vercel).
   - **A** en apex `@` → IPs que indique Vercel para el root domain, **o** usar **ALIAS/ANAME** si tu DNS lo permite apuntando a Vercel.

### `api` → Railway

1. En **Railway → Service → Settings → Networking**, genera un **dominio custom** `api.tudominio.com` (Railway te dará un target CNAME).
2. En tu DNS:
   - **CNAME** `api` → el hostname que indique Railway (p. ej. `xxxx.up.railway.app` o el CNAME que te den).

**No** uses un registro **A** fijo hacia Railway salvo que la plataforma lo documente; lo habitual es **CNAME** al endpoint que Railway asigne.

Tras propagar DNS (minutos–48 h), actualiza `CORS_ALLOW_ORIGINS` y `NEXT_PUBLIC_API_URL` con las URLs HTTPS definitivas.

### Go-live Fase 3.2 (TLS, CORS, Redis)

Checklist operativo (comandos `dig`/`openssl`/`curl`, Redis TLS, smoke): **`docs/operations/DEPLOY_FINAL_TLS_CHECKLIST.md`**.  
Validación local de variables (sin red): `cd backend && PYTHONPATH=. python scripts/check_deploy_infra_readiness.py` (opción `--strict` en producción).

---

## 5. PgBouncer (alta concurrencia / self‑hosted Postgres)

Si despliegas Postgres propio (no solo Supabase API) y el backend usa **SQLAlchemy** contra Postgres, coloca **PgBouncer** delante para evitar saturar `max_connections` (p. ej. stress tests con muchos workers).

- Configuración de referencia: `infra/pgbouncer/pgbouncer.ini` (`pool_mode = transaction`, `max_client_conn = 1000`, etc.).
- **Producción** (`ENVIRONMENT=production`): sin `DATABASE_URL` explícita, el backend construye la URI con host **`pgbouncer`** y puerto **`6432`** si existen `POSTGRES_USER`, `POSTGRES_PASSWORD` y `POSTGRES_DB` (o `POSTGRES_DATABASE`). Sobrescribible con `POSTGRES_HOST` / `POSTGRES_PORT`.
- El parámetro documental `?prepared_statements=false` **no** es válido en la URI de psycopg; el proyecto aplica el equivalente en `backend/app/db/session.py` (`prepare_threshold=0` + `pool_pre_ping=True`).
- Desarrollo local: `docker compose up` en la raíz del repo (servicios `postgres`, `pgbouncer`, `backend`). Ver `infra/pgbouncer/README.md`.

---

## 6. VeriFactu / base de datos (Supabase producción)

Ejecuta en el **SQL Editor** de Supabase, **en orden**, sobre la base de **producción**:

1. `backend/migrations/20260319_gastos_fiscal_verifactu.sql` — campos fiscales en `gastos`.
2. `backend/migrations/20260321_facturas_verifactu_f1.sql` — columnas VeriFactu en `facturas`.
3. `backend/migrations/20260322_auditoria_api_columns_facturas_immutability.sql` — columna `timestamp` en `auditoria` + trigger de inmutabilidad en `facturas` bloqueadas.
4. `backend/migrations/20260323_rename_columns_legacy_to_api.sql` — **RENAME** `empresas` (`nombre_legal`/`nombre_comercial` → nombres sin `_`) y ajustes `flota`; ver `backend/migrations/README_SCHEMA_SYNC.md`.
5. `backend/migrations/20260324_rls_tenant_current_empresa.sql` — **RLS** por `app.current_empresa_id` / `app.empresa_id` y `set_empresa_context` (text + uuid). **Atención:** con JWT `anon` las políticas filtran por tenant; el panel `/admin` en FastAPI debe usar **service role** en el servidor o políticas extra para admins, o devolverá listas vacías.

Si partes de `supabase_schema.sql`, asegúrate de que existan tablas `facturas` y `auditoria` compatibles con el código antes del paso 3.

---

## 7. Verificación rápida

- `GET https://api.tudominio.com/health` → `{"status":"ok"}`
- Frontend cargando datos con JWT y sin errores CORS en consola del navegador.
- Tras emitir una factura, comprobar filas en `auditoria` y campos `hash_registro` / `num_factura` en `facturas`.
