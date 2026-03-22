# Dossier Técnico Estructural — AB Logistics OS

**Documento:** valoración técnica (M&A / pre-seed)  
**Alcance:** Backend FastAPI, Frontend Next.js, migraciones SQL Supabase/PostgreSQL  
**Versión código de referencia:** monorepo con `backend/` (API), `frontend/` (SPA), `backend/migrations/` (DDL/RLS)  
**Fecha de redacción:** 2026-03-22  

---

## 1. Resumen de arquitectura

### 1.1 Stack tecnológico

| Capa | Tecnología | Evidencia en código |
|------|------------|---------------------|
| **API** | **FastAPI** (ASGI), Uvicorn | `app.main:create_app`, routers bajo `/auth`, `/portes`, `/facturas`, `/finance`, `/eco`, `/reports`, etc. |
| **Cliente** | **Next.js 16** (App Router), **React 19**, **TypeScript 5**, **Tailwind CSS 4** | `frontend/package.json` |
| **Datos** | **Supabase** (PostgREST + Postgres) vía cliente async propio | `app.db.supabase`, variables `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` |
| **Contenedor API** | **Docker** multi-stage, usuario no root, healthcheck `/ready` | `Dockerfile` (raíz repo) |
| **Observabilidad** | **Sentry** (opcional por `SENTRY_DSN`) | `app.main` inicializa `sentry_sdk` con integraciones FastAPI/Starlette |

El backend expone **OpenAPI** en `/docs` y `/redoc`. La configuración está centralizada en `app.core.config.Settings` (dataclass inmutable, caché LRU) con separación explícita **development / production** (CORS, cookies seguras, HSTS vía middleware).

### 1.2 Estrategia multi-tenant

**Modelo:** cada fila operativa lleva **`empresa_id`** (UUID en esquemas Pydantic y contrato API); el **contexto de tenant** se inyecta en la sesión de base de datos mediante la función RPC **`set_empresa_context(p_empresa_id)`**, que publica:

- `app.empresa_id`
- `app.current_empresa_id`

**Row Level Security (RLS):** la migración `20260324_rls_tenant_current_empresa.sql` habilita RLS en tablas nucleares (`portes`, `facturas`, `gastos`, `flota`, `presupuestos`, etc.) con políticas del tipo:

```text
USING (empresa_id::text = public.app_current_empresa_id())
WITH CHECK (idem)
```

La función auxiliar **`app_current_empresa_id()`** unifica lectura de sesión. El backend reafirma el contexto tras autenticación y antes de escrituras sensibles (`bind_write_context` en `app.api.deps`), alineado con documentación de seguridad multi-tenant.

**Implicación para due diligence:** el aislamiento lógico está **reforzado en base de datos**, no solo en filtros de aplicación — requisito típico de SaaS B2B y auditorías.

### 1.3 Integridad de persistencia

- **Soft delete:** patrón unificado `deleted_at IS NULL` = activo; helper `filter_not_deleted()` y `soft_delete_payload()` en `app.db.soft_delete`. Lecturas de listados en servicios operativos (portes, gastos, flota, clientes, etc.) aplican el filtro explícito.
- **Tipos de clave:** contrato API alineado con Postgres — **`UUID`** para perfiles, empresas, clientes, portes (donde aplique); **`BIGINT` / `int`** para **`facturas.id`** y referencias rectificativas en esquemas Pydantic (`FacturaOut`, `PorteOut.factura_id`), con documentación en `README_SCHEMA_SYNC.md` sobre coherencia con migraciones.
- **Inmutabilidad fiscal:** triggers SQL (`prevent_locked_factura_verifactu_mutate`) impiden mutar huella y numeración VeriFactu cuando `bloqueado` es verdadero — coherente con exigencias de trazabilidad e integridad de registro.

---

## 2. Núcleo legal y fiscal (moat regulatorio)

### 2.1 VeriFactu / SIF (diseño alineado AEAT, cadena de registros)

El **`VerifactuService`** implementa un **motor determinista** de huella:

- Normalización de NIF, fecha ISO, total con dos decimales.
- Cadena canónica para SHA-256:  
  `NIF_E + NIF_C + NumFactura + Fecha + Total + [|T:TIPO][|RECT:NUM_ORIG] + HashAnterior_hex`  
  (segmentos opcionales para rectificativas, documentado en código).
- **`generar_hash_factura`** y lectura del **último hash + siguiente secuencial** por empresa (`obtener_ultimo_hash_y_secuencial`) para encadenamiento.
- Eventos de auditoría best-effort (`registrar_evento`) y integración con generación de factura desde portes en **`FacturasService`**.

**Inmutabilidad en BD:** además de `bloqueado`, triggers impiden alterar campos críticos una vez sellado el registro (ver migración `20260322_auditoria_api_columns_facturas_immutability.sql`).

**Facturas rectificativas (R1):** `emitir_factura_rectificativa` emite importes negativos, clona snapshot con importes negados, encadena `hash_anterior` al hash de la F1 original, y numera serie rectificativa configurable por entorno.

> **Nota de due diligence:** la solución está **preparada para un modelo VeriFactu de encadenamiento e inmutabilidad**; la conformidad formal con normativa AEAT en vigor y certificación de software exige revisión legal y, si aplica, homologación/herramientas oficiales en la ventana temporal de obligatoriedad (p. ej. calendario 2025–2026).

### 2.2 Ley Crea y Crece / inmutabilidad

El producto refuerza **inmutabilidad de facturas selladas** a dos niveles:

1. **Aplicación:** facturas bloqueadas; rectificativas como nuevos registros encadenados, no edición in-place de la F1.
2. **Base de datos:** trigger ante `UPDATE` que bloquea cambios en huella/numeración si `bloqueado`.

Esto es coherente con el espíritu de **integridad del registro de facturación** y trazabilidad ante inspección.

---

## 3. Motor financiero y ESG

### 3.1 “Math engine” / EBITDA operativo aproximado

**`FinanceService`** documenta criterios explícitos **sin IVA**:

- **Ingresos:** suma de `base_imponible` en facturas emitidas; fallback `total_factura - cuota_iva`.
- **Gastos:** `total_eur` / `total_chf` menos cuota `iva` cuando existe; si no hay IVA desglosado, se asume neto.
- **EBITDA** ≈ ingresos netos − gastos netos (aproximación operativa), con agregación mensual para dashboards.

No sustituye a un ERP contable cerrado, pero **formaliza la lógica en un único servicio** — ventaja para auditoría de código y evolución.

**Snapshots operativos:** las facturas generadas desde portes almacenan **`porte_lineas_snapshot`** y **`total_km_estimados_snapshot`** — congelación fiscal/operativa al momento de emisión, independiente de cambios posteriores en portes.

### 3.2 Módulo sostenibilidad (ESG)

**`EcoService`** combina:

- Proxy de **digitalización** (tickets, papel ahorrado, CO₂ asociado a flujos legacy).
- **Scope 1 combustible:** gastos con categoría **`COMBUSTIBLE`** → estimación de litros (`neto EUR / precio referencia EUR/L`) × **kg CO₂/L** (configurable por entorno).
- Simulador de flota y resúmenes agregados para UI y reporting.

El frontend de sostenibilidad consume endpoints bajo `/eco` con autenticación y **credentials** incluidos, alineado con políticas de cookies/sesión.

---

## 4. Búnker de seguridad e identidad

### 4.1 Contraseñas: Argon2id + migración lazy

- **`hash_password_argon2id`** con parámetros documentados (tiempo, memoria, paralelismo).
- **`verify_password_against_stored`:** acepta hashes **Argon2** o legado **SHA-256 hex**; si el login es válido con legado, **`_lazy_upgrade_password_hash`** reescribe a Argon2.

Esto reduce riesgo de deuda de seguridad heredada sin forzar reset masivo de usuarios.

### 4.2 JWT y sesiones

- **Access token** JWT (HS256) con `python-jose`; compatibilidad dual con **Supabase Auth** (`aud=authenticated`, `iss` configurable) y JWT propio de `/auth/login`.
- **Refresh tokens:** opacos, almacenados como **SHA-256** (`hash_refresh_token`), rotación en **`RefreshTokenService`**, reutilización detectada con ventana de gracia; reuso abusivo → **`revoke_all_for_user`** y alerta a **Sentry** (`_sentry_security_alert`).
- Metadatos de sesión: **IP** y **User-Agent** truncado/legible (`user_agent_parser`) para listados de sesiones activas y revocación por dispositivo (esquema `ActiveSessionOut` / flujos en servicio).

### 4.3 Defensa en profundidad HTTP

- Middleware de **cabeceras de seguridad** (HSTS en producción).
- **CORS** parametrizado por origen y regex (previews).
- **JsonAccessLog** para trazas estructuradas de acceso.

---

## 5. Estrategia de producto (UX / PLG)

### 5.1 Calculadora de presupuestos y login-wall

- Página **`/presupuestos`**: flujo de **captación** con detección de sesión vía **`jwt_token` en `localStorage`** (consistente con el resto del front).
- Antes de llamar a **`POST /presupuestos/calcular`**, si no hay sesión se muestra un **modal** (“Guarda tu Presupuesto”) con CTA a login; **no se dispara** la petición al backend.
- **Preservación de estado:** borrador serializado en **`sessionStorage`** (`presupuestoDraft` helpers) antes de navegar a **`/login?redirect=/presupuestos`**; restauración al volver con feedback al usuario.

Este patrón reduce abandono en flujos PLG y mantiene **trazabilidad exigible** solo tras autenticación (coherente con backend que resuelve `empresa_id` desde token).

---

## 6. Calidad de código y operaciones

### 6.1 Validación y contratos

- **Pydantic v2** en todos los esquemas de entrada/salida (`schemas/`), incluyendo **`UUID`** validados para IDs de tenant y **`int`** para PKs BIGINT de facturas donde aplica.
- Separación clara **Create / Out / Update** en maestras (`cliente`, `empresa`, `proyectos`, `inventario` donde existan).

### 6.2 Frontend

- **TypeScript estricto**; componentes cliente explícitos (`"use client"`).
- **ToastHost** centralizado (`components/ui/ToastHost.tsx`) para feedback no bloqueante sin añadir dependencias pesadas de notificaciones — patrón sustituible por Sonner u otra lib si se escala diseño sistema.

### 6.3 Observabilidad y despliegue

- **Sentry** opcional en API y dependencias `@sentry/*` en frontend para errores de cliente.
- **Dockerfile** production-ready: multi-stage, usuario no privilegiado, `HEALTHCHECK` contra `/ready`, variable `PORT` estándar (Railway/Kubernetes).

### 6.4 Posición para due diligence (escala enterprise)

| Fortaleza | Descripción |
|-----------|-------------|
| **Separación de capas** | Servicios por dominio (facturas, eco, finance, auth, flota…), sin lógica fiscal mezclada en controladores. |
| **Migraciones versionadas** | SQL explícito para RLS, triggers, columnas fiscales — reproducible en entornos staging/prod. |
| **Seguridad de identidad** | Argon2id, rotación de refresh, detección de reuso, headers y CORS configurables. |
| **Extensibilidad** | Nuevos módulos como routers FastAPI + esquemas Pydantic; front modular por rutas App Router. |

**Matizar con rigor de CTO:** cualquier producto en evolución tiene **tareas de endurecimiento** (tests E2E adicionales, cobertura de contrato OpenAPI, hardening de políticas RLS en despliegues con rol `anon` vs `service_role`, revisión de migraciones legacy vs tipos BIGINT/UUID). La base actual **no presenta deuda arquitectónica grave**: patrones coherentes, seguridad y fiscalidad abordados de forma explícita y documentada — **base sólida para escalar** hacia entornos enterprise con inversión incremental en QA y compliance formal.

---

## Anexo A — Inventario rápido de routers API (backend)

| Prefijo | Dominio |
|---------|---------|
| `/auth` | Login, refresh, sesiones |
| `/portes`, `/clientes` | Operativa logística y maestros |
| `/facturas` | Emisión, rectificativas |
| `/gastos` | Gastos y OCR hints |
| `/finance`, `/dashboard` | KPIs y resúmenes |
| `/reports` | PDFs inmutables, certificados ESG |
| `/eco` | Resumen, simulador, certificados |
| `/flota` | Inventario, taller, amortización |
| `/presupuestos` | Cálculo VeriFactu-presupuesto |
| `/admin` | Panel SaaS (empresas, usuarios, métricas) |

---

## Anexo B — Referencias de archivos clave

- API: `backend/app/main.py`, `backend/app/api/deps.py`, `backend/app/core/config.py`, `backend/app/core/security.py`
- Fiscal: `backend/app/services/verifactu_service.py`, `backend/app/services/facturas_service.py`
- Finanzas: `backend/app/services/finance_service.py`
- ESG: `backend/app/services/eco_service.py`
- Sesiones: `backend/app/services/refresh_token_service.py`
- RLS: `backend/migrations/20260324_rls_tenant_current_empresa.sql`
- Inmutabilidad facturas: `backend/migrations/20260322_auditoria_api_columns_facturas_immutability.sql`
- Contenedor: `Dockerfile`
- PLG presupuestos: `frontend/src/app/presupuestos/page.tsx`, `frontend/src/lib/presupuestoDraft.ts`, `frontend/src/app/login/page.tsx`

---

*Fin del dossier técnico estructural — AB Logistics OS.*
