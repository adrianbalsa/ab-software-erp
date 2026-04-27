# Contratos de plataforma y reducción de dependencias

Documento operativo para **due diligence**, integradores (app móvil, B2B) y migraciones de
infraestructura **sin romper** el producto actual. Orden de prioridad alineado al riesgo.

## 1. Contrato HTTP público (API)

- **Rutas estables para nuevos clientes:** prefijo **`/api/v1/`**. Ejemplos usados por integración
  móvil planificada: portes, gastos/OCR, portal cliente (`docs/MOBILE_ARCHITECTURE.md`).
- **Rutas sin prefijo** (`/portes`, `/auth`, `/facturas`, …): compatibilidad con el frontend y
  clientes legacy; **no** deben ser el objetivo de nuevas integraciones externas.
- **Versionado:** incrementar solo con cambios incompatibles (nuevo prefijo `/api/v2` o
  deprecación documentada). El número de versión de OpenAPI (`app/openapi_config.API_VERSION`)
  refleja la especificación publicada; no sustituye el prefijo de URL.
- **Autenticación:** `Authorization: Bearer <JWT>` (y cookies HttpOnly en mismo sitio) según
  OpenAPI. El emisor del JWT puede ser Supabase Auth o login propio (`POST /auth/login`); el
  contrato del **token** (claims usados por el backend) es lo que deben respetar los clientes.

## 2. Secretos e integraciones sensibles

- **Interfaz única:** `get_secret_manager()` — inventario y runbook en `README_SECURITY.md`.
- **Config de arranque no secreta:** `get_settings()` (`app/core/config.py`) para CORS, URLs de
  despliegue, flags fiscales, etc. Evitar duplicar secretos nuevos en `Settings` cuando exista
  clave equivalente en el gestor.

## 3. Base de datos (Postgres / Supabase)

- **Contrato técnico:** SQLAlchemy / cliente Supabase usan **`DATABASE_URL`** (Postgres estándar).
  El proyecto puede usar Postgres hospedado en **Supabase**, en **Railway**, o en otro proveedor;
  ver matriz en `docs/INFRASTRUCTURE.md` §1 y §7.
- **RLS:** hoy aplicado vía Supabase con JWT por request. Un cambio de proveedor de Postgres
  implica replicar políticas de aislamiento **en aplicación o en Postgres**; no es un cambio de
  variable de entorno aislado.
- **Lock-in consciente:** Storage, Realtime y Auth “de marca” Supabase son dependencias
  adicionales; el menor acoplamiento se consigue manteniendo la lógica de negocio en **servicios**
  y en esta API, no en triggers no documentados fuera del repo.

## 4. Autenticación (límite del proveedor)

- **Punto de acoplamiento:** validación de JWT (`SUPABASE_JWT_SECRET`, issuer) y clientes con
  service role solo donde corresponda (`deps.get_db_admin` para login/refresh).
- **Migración futura** (solo cuando haya requisito comercial): sustituir emisor de JWT manteniendo
  mismos claims necesarios (`sub`, `empresa_id`, roles, etc.) y una ventana de doble emisión +
  pruebas E2E. Fuera de alcance mientras no se defina el proveedor objetivo.

## 5. Trabajos en segundo plano (cola)

- **Implementación actual:** ARQ + Redis (`REDIS_URL`).
- **Punto de entrada único en código:** `app/core/job_queue.py` — los servicios de dominio deben
  importar funciones de encolado desde ahí, no instanciar Redis/ARQ directamente. Facilita sustituir
  el broker (p. ej. cola administrada) sin tocar VeriFactu ni facturación.
- **Worker:** mismo repositorio, proceso separado (`infra/railway/worker.railway.json`).
- **HA / retry / observabilidad:** `docs/operations/REDIS_001_HA_BILLING_QUEUE.md`.

## 6. Pagos y webhooks (Stripe / GoCardless)

- **Contrato:** firma de webhook (cabeceras documentadas por cada proveedor) y manejadores en
  `stripe_service` / rutas `api/v1`. Los proveedores son dependencias de negocio inevitables.
- **Idempotencia (implementado):** columna ``webhook_events.external_event_id`` + índice único
  ``(provider, external_event_id)`` (migración ``20260419203000_webhook_events_external_event_id``).
  - **Stripe:** `claim_webhook_event` antes de mutar ``empresas``; duplicado →
    ``{"received": True, "duplicate": True}``; si el handler falla, se borra el claim para reintento.
  - **GoCardless:** mismo claim por ``events[].id``; segundo envío omite marca de cobro / mandato
    y auditorías duplicadas para ese id.
- **Tests:** `backend/tests/unit/test_webhook_idempotency.py`.

## 7. Infraestructura como código y despliegue

- **Railway + Terraform:** `docs/INFRASTRUCTURE.md`, `infra/terraform/`, `.github/workflows/deploy.yml`.
- **Variables y CORS:** `docs/DEPLOYMENT.md`.

## Impacto en valoración y funcionamiento

- **Valoración / DD:** tener este documento y rutas `/api/v1` claras reduce **riesgo percibido** de
  lock-in y acelera revisiones técnicas.
- **Funcionamiento:** los cambios “blandos” (documentación + fachada `job_queue`) no alteran
  comportamiento en runtime. Los cambios “duros” (cambiar Auth o RLS) requieren proyecto dedicado
  y pruebas de regresión completas.
