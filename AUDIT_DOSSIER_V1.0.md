# Auditoría Integral — Dossier de Entrega v1.0

## 1) Identificación del sistema a auditar

- Producto: AB Logistics OS.
- Repositorio: `Scanner`.
- Arquitectura base:
  - Backend: FastAPI (`backend/app/main.py`).
  - Frontend: Next.js (`frontend/package.json`).
  - Datos: Supabase/Postgres (`supabase/migrations/*`).
  - Proxy: Nginx (`infrastructure/nginx/default.conf`).
  - Cache/colas/rate limiting: Redis (`docker-compose.yml`).
- Dominio funcional: fiscalidad (VeriFactu), seguridad de acceso multitenant, BI financiero, ESG, banking, asistente IA.

## 2) Objetivo de la auditoría

- Validar cumplimiento técnico, operativo y de seguridad de AB Logistics OS en:
  - Integridad fiscal (VeriFactu, cadena de hash, inmutabilidad).
  - Seguridad de aplicación y datos (RLS/RBAC/JWT/auditoría).
  - Resiliencia operativa (healthchecks, dependencia crítica, endurecimiento HTTP/TLS).
  - Trazabilidad ESG.
  - Trazabilidad financiera/BI y coherencia de métricas.
  - Gobierno de secretos e integración IA.

## 3) Alcance técnico (incluido en esta auditoría)

- API backend y middlewares de seguridad.
- Modelo y migraciones de base de datos en Supabase/Postgres.
- Configuración de despliegue containerizado (Docker Compose).
- Configuración Nginx para capa de entrada.
- Frontend de consumo de APIs críticas (BI, chat, export).
- Servicios críticos:
  - Fiscalidad/VeriFactu.
  - ESG.
  - BI.
  - Banking/reconciliación.
  - IA/LogisAdvisor.

## 4) Exclusiones explícitas (requieren evidencia adicional externa)

- Estado real de producción (infra cloud, dominios, WAF/CDN, hardening host).
- Evidencias legales/financieras corporativas fuera del repo.
- Evidencia de operación real (SIEM, SOC, monitorización histórica, incidentes cerrados).

## 5) Evidencias técnicas ya disponibles (repositorio)

### 5.1 Stack, runtime y wiring

- `backend/app/main.py`: creación de app, middlewares, rutas, health/readiness, rate limiting.
- `backend/app/core/config.py`: configuración de entorno, CORS, hosts, seguridad, claves e integraciones.
- `docker-compose.yml`: servicios `redis`, `backend`, `frontend`, `nginx`.
- `infrastructure/nginx/default.conf`: TLS 1.2/1.3, HSTS, cabeceras de seguridad, redirección HTTPS.

### 5.2 Fiscalidad y cumplimiento VeriFactu

- `backend/app/core/verifactu_hashing.py`: hash canónico único (`CanonicalHashService`).
- `backend/app/core/math_engine.py`: precisión `Decimal`, cuantización y consistencia de redondeo.
- `backend/app/core/xades_signer.py`: firma XAdES.
- `backend/app/api/v1/verifactu.py`: endpoints fiscales.
- `supabase/migrations/20260429090000_compliance_final_guardrail.sql`: inmutabilidad estricta de tablas/filas fiscales.
- `backend/tests/unit/test_verifactu_*`, `backend/tests/test_verifactu_*`: pruebas fiscales y cadena hash.

### 5.3 Seguridad de acceso, aislamiento y trazabilidad

- `backend/app/middleware/tenant_rbac_context.py`: fijación obligatoria de contexto tenant/RBAC.
- `backend/app/middleware/audit_log_middleware.py`: trazabilidad de operaciones autenticadas.
- `backend/app/core/rate_limit.py` y middlewares de rate limit (`backend/app/middleware/*rate_limit*`).
- `supabase/migrations/20260429120000_esg_period_snapshots_km_quality.sql`: políticas RLS con `public.app_current_empresa_id()` y `public.app_rbac_role()`.

### 5.4 ESG y snapshots de periodo

- `backend/app/services/esg_service.py`: cálculo CO2, auditoría ESG, snapshots, bloqueo de mutación tras cierre.
- `supabase/migrations/20260429120000_esg_period_snapshots_km_quality.sql`: tabla `esg_period_snapshots`, inmutabilidad y bloqueo de cambios en `portes`.

### 5.5 BI y visualización

- `backend/app/api/v1/bi.py`: endpoints BI.
- `backend/app/services/bi_service.py`: agregados BI y salud financiera.
- `frontend/src/app/(dashboard)/bi/financial/page.tsx`: visualización Recharts + export PDF/CSV.
- `frontend/src/lib/export-to-csv.ts`: exportación CSV.

### 5.6 IA y secretos

- `backend/app/services/advisor_service.py`: LogisAdvisor con LiteLLM y fallback de proveedor.
- Endpoint IA canónico activo: `backend/app/api/v1/advisor.py` (`POST /api/v1/advisor/ask`).
- `backend/app/services/secret_manager_service.py`: backends `env`, `vault`, `aws secretsmanager`.
- `frontend/src/components/dashboard/LogisAdvisorChat.tsx`: streaming SSE en frontend.

### 5.7 Banking/reconciliación

- `backend/app/api/v1/banking.py`: conexión bancaria PSD2, sync, reconciliación fuzzy/IA.

## 6) Matriz de control para el equipo auditor

## 6.1 Integridad fiscal (P1)

- Control: función de hash única y determinista.
  - Evidencia: `backend/app/core/verifactu_hashing.py`.
  - Verificación auditor: reproducir vectores de prueba y comparar hash esperado.
- Control: inmutabilidad de registros sellados.
  - Evidencia: `supabase/migrations/20260429090000_compliance_final_guardrail.sql`.
  - Verificación auditor: intento de `UPDATE/DELETE/TRUNCATE` en datos sellados debe fallar.
- Control: aritmética fiscal en decimal.
  - Evidencia: `backend/app/core/math_engine.py`.
  - Verificación auditor: tests de redondeo y consistencia `base + iva (+ re - irpf)`.

## 6.2 Seguridad de aplicación y datos (P1)

- Control: contexto tenant/RBAC obligatorio por request autenticada.
  - Evidencia: `backend/app/middleware/tenant_rbac_context.py`.
  - Verificación auditor: requests sin contexto válido deben responder 403.
- Control: auditoría de operaciones mutantes/autenticadas.
  - Evidencia: `backend/app/middleware/audit_log_middleware.py`.
  - Verificación auditor: generar eventos y verificar persistencia en tabla de auditoría.
- Control: rate limiting multicapa.
  - Evidencia: `backend/app/middleware/rate_limit_middleware.py`, `backend/app/middleware/fiscal_rate_limit_middleware.py`.
  - Verificación auditor: pruebas de ráfaga por IP, tenant y bucket fiscal.
- Control: RLS por empresa y rol.
  - Evidencia: migraciones en `supabase/migrations/*`.
  - Verificación auditor: test de acceso cruzado entre tenants (debe denegarse).

## 6.3 Endurecimiento de perímetro y transporte (P1/P2)

- Control: TLS y cabeceras de seguridad en Nginx.
  - Evidencia: `infrastructure/nginx/default.conf`.
  - Verificación auditor: escaneo SSL externo + validación cabeceras HTTP.
- Control: redirección forzada HTTP->HTTPS.
  - Evidencia: `infrastructure/nginx/default.conf`.

## 6.4 ESG y trazabilidad (P2)

- Control: snapshot mensual inmutable y bloqueo posterior de mutación.
  - Evidencia: `supabase/migrations/20260429120000_esg_period_snapshots_km_quality.sql`.
  - Verificación auditor: cierre mensual + intento de modificación posterior en `portes`.
- Control: procedencia km y cobertura de calidad.
  - Evidencia: `backend/app/services/esg_service.py` + columnas `esg_km_source`.

## 6.5 BI/finanzas (P2)

- Control: agregados BI reproducibles por API.
  - Evidencia: `backend/app/api/v1/bi.py`, `backend/app/services/bi_service.py`.
  - Verificación auditor: recalcular muestras y comparar respuesta API.
- Control: export de datos de reporting.
  - Evidencia: `frontend/src/lib/export-to-csv.ts`.

## 6.6 IA y gobierno de secretos (P2)

- Control: resolución de secretos vía servicio centralizado.
  - Evidencia: `backend/app/services/secret_manager_service.py`.
  - Verificación auditor: pruebas por backend (`env/vault/aws`) y fallback.
- Control: proveedores IA y fallback de modelos.
  - Evidencia: `backend/app/services/advisor_service.py`.
  - Verificación auditor: simular indisponibilidad de proveedor primario y comprobar fallback.

## 7) Estado funcional relevante para auditoría

- Fiscalidad VeriFactu: implementada con controles de integridad e inmutabilidad en código y SQL.
- Seguridad multitenant: implementada (middleware + RLS).
- BI y ESG: implementados con endpoints y visualizaciones activas.
- IA: operativa en dos canales backend (`advisor` y `chatbot`) y dos UIs frontend.
- Banking: endpoints de conexión/sync/reconciliación disponibles.

## 8) Riesgos abiertos identificables desde código (para validar en auditoría)

- No hay evidencia en repo de resultado externo de calificación SSL Labs "A+"; requiere prueba externa.
- La unificación IA bajo `LogisticsBrainContextService` no está implementada con ese nombre en el código actual.
- Coexistencia de dos UIs/chat flows para IA (streaming SSE y no streaming) requiere validación de consistencia funcional y de control.

## 9) Documentación y evidencias adicionales requeridas (adjuntar para auditoría completa)

- Inventario de activos productivos (infra, dominios, IPs, entornos).
- Evidencias de producción:
  - resultados de escaneo TLS/SSL externo,
  - cabeceras HTTP verificadas en producción,
  - backup/restore test report,
  - DR test report,
  - incident log de últimos 12 meses.
- Seguridad:
  - último pentest,
  - dependencia CVE report,
  - política de rotación de secretos y evidencias de rotación real.
- Cumplimiento legal/fiscal:
  - política de retención,
  - procedimientos operativos firmados,
  - evidencias regulatorias aplicables.
- Finanzas/empresa:
  - estados financieros y conciliaciones cerradas del periodo auditado.

## 10) Protocolo de ejecución recomendado para el auditor

- Fase 1 — Revisión estática:
  - validar estructura, migraciones, middlewares y controles declarados.
- Fase 2 — Reproducción técnica en entorno controlado:
  - desplegar `docker-compose.yml`,
  - ejecutar pruebas de seguridad, RLS, inmutabilidad fiscal, rate limiting.
- Fase 3 — Verificación de evidencia operativa:
  - contrastar reportes externos (SSL, pentest, backups, DR, monitorización).
- Fase 4 — Informe final:
  - matriz de cumplimiento por control,
  - hallazgos,
  - severidad,
  - plan de remediación.

## 11) Entregables esperados por parte del auditor

- Informe técnico de hallazgos (detallado por control y severidad).
- Informe ejecutivo de cumplimiento y riesgos.
- Lista de no conformidades y acciones correctivas.
- Evidencia de pruebas reproducibles (scripts/comandos/resultados).
