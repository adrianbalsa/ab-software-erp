# Stack Técnico & Arquitectura

- Backend principal en `FastAPI` (`backend/app/main.py`) con arranque de contexto decimal global (`initialize_global_decimal_context`) y middleware de seguridad/cumplimiento.
- Frontend en `Next.js` App Router (`frontend/package.json` con `next@16.1.7`, `react@19.2.3`).
- Persistencia en `Supabase/Postgres` con uso de tablas `public.*`, migraciones SQL en `supabase/migrations/*` y políticas RLS por tenant/rol.
- Proxy/reverse proxy en `Nginx` (`infrastructure/nginx/default.conf`) con upstreams `backend:8000` y `frontend:3000`.
- `Redis` operativo en `docker-compose.yml` (`redis:7-alpine`) para rate limiting/caché/colas.
- Hardening HTTP activo:
  - Rate limiting multicapa en backend (`GlobalIPRateLimitMiddleware`, `TenantRateLimitMiddleware`, `EndpointCostRateLimitMiddleware`, `BIRateLimitMiddleware`, `FiscalVerifactuRateLimitMiddleware`).
  - Límites específicos visibles en código: auth `10/min`, global IP `100/min`, BI `30/min`, fiscal AEAT `10/min`.
  - Cabeceras de seguridad y TLS en Nginx: `TLSv1.2/TLSv1.3`, `HSTS`, `X-Frame-Options`, `X-Content-Type-Options`, redirección HTTP->HTTPS.
- Estado SSL A+: no hay evidencia explícita en el repositorio de una validación/documentación de grado SSL Labs "A+"; sí existe configuración TLS endurecida.

# Módulos Core Implementados (v1.0)

- Fiscalidad (VeriFactu / XAdES-BES / inalterabilidad):
  - Endpoint fiscal dedicado `POST/GET` bajo `/api/v1/verifactu` (`backend/app/api/v1/verifactu.py`).
  - Hash canónico único en `backend/app/core/verifactu_hashing.py` (`CanonicalHashService.generate_verifactu_hash`) con SHA-256.
  - Motor fiscal/contable `MathEngine` en `backend/app/core/math_engine.py` usando `Decimal`, `ROUND_HALF_UP`, cuantización explícita, y checks de integridad de redondeo.
  - Firma XAdES en `backend/app/core/xades_signer.py` y tests unitarios dedicados (`backend/tests/unit/test_xades_signer.py`).
  - Guardrails de inmutabilidad fiscal en migración `supabase/migrations/20260429090000_compliance_final_guardrail.sql` (bloqueo UPDATE/DELETE/TRUNCATE en filas selladas/hash).

- Seguridad (RLS / RBAC / auditoría JWT):
  - Middleware `TenantRBACContextMiddleware` fuerza contexto tenant+rol por token antes de ejecutar lógica de negocio.
  - RLS por empresa/rol con funciones `public.app_current_empresa_id()` y `public.app_rbac_role()` en migraciones (ej. `esg_period_snapshots_select/insert`).
  - Auditoría de requests autenticadas en `AuditLogMiddleware` hacia `public.audit_logs` vía `AuditLogsService`.
  - Validación JWT central y normalización de claims/roles en backend y frontend (`decode_access_token_payload`, utilidades JWT en `frontend/src/lib/api.ts`).

- BI & Visualización:
  - API BI implementada en `/api/v1/bi/*` (`dashboard/summary`, `charts/profitability`, `charts/esg-impact`, `financial-health`).
  - Servicio BI (`backend/app/services/bi_service.py`) con agregados para Recharts y SQL directo para salud financiera.
  - Frontend BI financiero activo en `frontend/src/app/(dashboard)/bi/financial/page.tsx` usando `recharts`.
  - Exportación CSV implementada en `frontend/src/lib/export-to-csv.ts`; exportación PDF en la página BI con `html2canvas` + `jsPDF`.

- ESG (trazabilidad CO2 / snapshots por periodo):
  - Cálculo ESG operativo en `backend/app/services/esg_service.py` con factor ISO 14083 diesel (`2.67 kg/L`) y datos de ruta (`MapsService` + fallback).
  - Cierre de periodo ESG implementado (`close_esg_period_snapshot`) con hash de contenido `content_sha256`, snapshot y bloqueo posterior de mutación.
  - Migración `20260429120000_esg_period_snapshots_km_quality.sql`:
    - Tabla `public.esg_period_snapshots` con unicidad por empresa/mes.
    - Trigger de inmutabilidad (append-only: sin UPDATE/DELETE).
    - Bloqueo de cambios CO2/distancias en `portes` cuando `esg_data_locked=true`.
    - Campos de calidad/cobertura de km por fuente (`route_api_meters`, `recorded_road_km`, `telemetry`, `estimated`).

# Estado del Asistente IA

- Estado de unificación de contexto:
  - Endpoint canónico único activo: `POST /api/v1/advisor/ask`.
  - El contexto operativo se centraliza en `gather_advisor_context` (`backend/app/services/advisor_service.py`).
  - Rutas legacy `chat.py` y `chatbot.py` retiradas del enrutado público.

- Proveedores activos/configurados en backend:
  - Resolución de claves por `SecretManagerService` (`OPENAI`, `Anthropic`, `Gemini`, `Azure OpenAI`).
  - `advisor_service.py` usa `LiteLLM` para multproveedor y fallback de modelo.
  - `chatbot.py` usa SDK `Anthropic` directo (`claude-3-5-sonnet-20241022`) con API key del secret manager.

- Estado frontend IA (Shadcn + streaming):
  - Dependencia `shadcn` declarada en `frontend/package.json` y uso de componentes `@/components/ui/*` en vistas/app.
  - Chat con streaming SSE activo para LogisAdvisor en `frontend/src/components/dashboard/LogisAdvisorChat.tsx` usando `streamAdvisorAsk` (`text/event-stream`).
  - Endpoint canónico único: `POST /api/v1/advisor/ask` (streaming SSE o respuesta JSON con `stream=false`).

# Deuda Técnica & Funcionalidades Pendientes

- Integración Google Maps API para km/rutas reales en ESG:
  - Estado actual: integración parcial activa (`MapsService`, `Maps_API_KEY`, uso en ESG/geo).
  - Brecha técnica existente: cobertura de fuentes km incluye `telemetry` como categoría, pero aparece como vía futura/no implementada end-to-end en el flujo actual.

- Integración Bancaria:
  - Estado actual: backend implementa conexión PSD2/GoCardless, sincronización, sugerencias y conciliación IA (`/api/v1/banking/*`).
  - Punto pendiente funcional identificado: consolidación final de experiencia operacional y cierre funcional completo según el backlog estratégico.

- UI completa del chat:
  - Estado actual: hay dos implementaciones de UI (una SSE avanzada y otra no streaming), lo que evidencia convivencia de capas de chat y falta de unificación completa de UX.

- Nuevos diagramas financieros:
  - Estado actual: dashboard BI financiero incluye gráficas P&L, rentabilidad, estructura de impacto y liquidez.
  - Pendiente solicitado: incorporación de nuevos diagramas financieros adicionales sobre la base ya desplegada.
