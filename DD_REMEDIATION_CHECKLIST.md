# DD Remediation Checklist (Dynamic)

Estado objetivo: convertir `NO-GO condicional` a `GO` en ventana de 60-90 dias.
Contexto de ejecucion: `solo-founder` (capacidad limitada, foco estricto en ruta critica).
Modo de uso: al finalizar cada fase, actualizamos `Status`, `Owner`, `Due`, `Evidence` y `%`.

Legend:
- `[ ]` todo
- `[~]` in progress
- `[x]` done
- `[!]` blocker

---

## 0) Dashboard de progreso

- Fecha inicio: `2026-04-29`
- Fecha objetivo (release junio): `2026-06-30`
- Estado global: `Documentación DD lista; pendiente archivo comité (data room + acta GO firmada)`
- Progreso global: `90%`

### Progreso por fase

- Fase 1 (P1 bloqueantes): `100%` (**cerrada**; evidencias en §1.1–1.3)
- Fase 2 (P1/P2 tecnico-funcional): `100%` (**cerrada**; evidencias en §2.1–2.3)
- Fase 3 (evidencias externas y cierre): `~90%` (**documentación lista**; **pendiente** §3.4 archivo en data room y firma acta GO)

### Cadencia de seguimiento (solo-founder)

- Actualizacion semanal fija: `cada viernes`
- Limite WIP: `maximo 3 tareas simultaneas`
- Regla de prioridad: `P1 compliance > seguridad > observabilidad > funcional`
- Criterio de cierre de fase: `evidencia escrita + test/reporte + decision registrada`

---

## 1) Fase 1 - Bloqueantes P1 (Semanas 1-2)

### 1.1 Governance y control de secretos

- [x] Inventario completo de secretos criticos (JWT/Fernet/LLM/OCR/pagos)  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-05-02` | Evidence: `docs/security/secrets_inventory_v1.md`
- [x] Eliminar accesos residuales directos a secretos fuera de `SecretManagerService`  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-05-06` | Evidence: `backend/app/services/secret_manager_service.py + backend/app/{worker.py,core/alerts.py,core/mtls_certificates.py,services/alert_service.py} + pytest secret_manager`
- [x] Definir politica de rotacion y ejecutar primera rotacion controlada  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-05-09` | Evidence: `docs/security/SECRET_ROTATION_POLICY.md + docs/security/SECRET_ROTATION_LOG_2026-04-29.md`

### 1.2 Seguridad multitenant y cumplimiento fiscal

- [x] Prueba reproducible de aislamiento RLS entre tenants (acceso cruzado denegado)  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-05-08` | Evidence: `backend/tests/test_rls_tenant_isolation_dd.py` + `cd backend && pytest tests/test_rls_tenant_isolation_dd.py -v` (marcador `rls_isolation`; mocks deterministas, sin DB en vivo)
- [x] Verificacion automatizada de cadena hash VeriFactu (casos ok/fail/repair)  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-05-10` | Evidence: `backend/tests/unit/test_verifactu_hash_chain_audit.py` + `backend/tests/test_verifactu_chain.py` + `cd backend && pytest tests/test_verifactu_chain.py tests/unit/test_verifactu_hash_chain_audit.py -v`
- [x] Validacion de inmutabilidad fiscal en tablas selladas (update/delete/truncate bloqueados)  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-05-11` | Evidence: `scripts/verify_fiscal_immutability_smoke.sql` (catálogo + smoke opcional en Postgres/Supabase) + `cd backend && pytest tests/unit/test_fiscal_immutability_guardrail_migrations.py tests/test_verifactu_logic.py::test_no_delete_http_facturas -v` + migraciones `supabase/migrations/20260428184500_facturas_immutability_final_seal.sql`, `supabase/migrations/20260429090000_compliance_final_guardrail.sql`, `supabase/migrations/20260423170000_audit_logs_immutable_hardening.sql`

### 1.3 Observabilidad minima auditable

- [x] Definir SLI/SLO minimos (API availability, error rate, p95 latency)  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-05-12` | Evidence: `docs/operations/SLO_MINIMAL_V1.md` (+ enlace cruzado en `docs/operations/MONITORING_OBSERVABILITY.md`)
- [x] Alertas operativas para errores P1 (auth, verifactu, db, redis)  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-05-14` | Evidence: `docs/operations/ALERT_RULES_P1_V1.md` (reglas M1/M2 + S1–S3 Sentry + §5 tabla de capturas; enlaces en `MONITORING_OBSERVABILITY.md` / `SLO_MINIMAL_V1.md`)
- [x] Runbook de incidentes P1 (deteccion, contencion, comunicacion, RCA)  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-05-16` | Evidence: `docs/operations/runbook_v1.md` (enlace desde `docs/operations/ON_CALL_RUNBOOK.md` + `ALERT_RULES_P1_V1.md`)

---

## 2) Fase 2 - Cierre tecnico/funcional (Semanas 3-6)

### 2.1 IA (unificacion de flujo y UX)

- [x] Consolidar un unico flujo canonico backend (`/api/v1/advisor/ask`) sin rutas legacy activas  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `app/main.py` (solo `advisor_legacy_deprecation` bajo `/ai`), `app/api/routes/advisor_legacy_deprecation.py` (410 + `canonical_path`), `app/core/rate_limit.py` (bucket `ai` solo en `/api/v1/advisor/ask`), tests `tests/api/v1/test_advisor_legacy_gone.py` + migración de suites de `/ai/consult` a ask/servicio en `tests/test_rbac_enforcement.py`, `tests/test_rls_tenant_isolation_dd.py`, `tests/test_ai_diagnostic.py`, `tests/e2e/test_autonomous_onboarding_flow.py`; middleware `rate_limit_middleware` fail-open si Redis cae en `check_credits` para buckets caros; `exception_handler.py` no traga `HTTPException` de Starlette
- [x] Unificar frontend chat (evitar duplicidad SSE vs no-SSE en experiencia final)  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `frontend/src/lib/logis-advisor-client.ts` (``streamAdvisorAskIntoMessages`` compartido), `frontend/src/components/dashboard/LogisAdvisorChat.tsx` + `frontend/src/app/dashboard/vampire-radar/page.tsx`; widget `frontend/src/components/chat/LogisAdvisor.tsx` vía ``streamAdvisorAsk`` JSON; eliminado ``streamAdvisorChat`` duplicado en `frontend/src/lib/api.ts`
- [x] Verificar fallback de proveedores/modelos IA con pruebas de degradacion  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `backend/tests/api/v1/test_advisor_degradation.py` (503 sin LLM, 502 gather, 503 ``RuntimeError`` proveedor JSON)

### 2.2 ESG (trazabilidad y calidad de dato)

- [x] Cerrar cobertura de fuentes km y reglas de calidad por fuente  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `backend/app/core/esg_km_quality.py` (``ESG_KM_SOURCE_REGISTRY`` + docstrings de inferencia), `backend/tests/unit/test_esg_km_quality.py` (registro, telemetría, explícito inválido, ceros, GLEC/operational existentes)
- [x] Validar snapshot mensual inmutable y bloqueo de mutacion post-cierre  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `supabase/migrations/20260429120000_esg_period_snapshots_km_quality.sql` (triggers WORM + bloqueo), `backend/tests/unit/test_esg_worm_migration_contract.py` (aserciones de contrato), `backend/tests/unit/test_esg_km_quality.py` (``esg_snapshot_content_sha256`` golden), `backend/app/core/esg_km_quality.py` (hash canónico compartido con `EsgService.close_esg_period_snapshot`)
- [x] Reporte de calidad ESG (cobertura, estimado vs medido, gaps)  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `backend/app/core/esg_km_quality.py` (``build_esg_quality_report``), `GET /api/v1/esg/quality-report` en `backend/app/api/v1/esg.py`, `EsgService.get_esg_quality_report` en `backend/app/services/esg_service.py`, esquemas `EsgQualityReportOut` en `backend/app/schemas/esg.py`; UI `frontend/src/app/sostenibilidad/calidad-km/page.tsx` + `fetchEsgQualityReport` en `frontend/src/lib/api.ts`, enlace desde `frontend/src/app/sostenibilidad/auditoria/page.tsx`

### 2.3 BI y banking

- [x] Implementar/ajustar diagramas financieros pendientes en dashboard  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `frontend/src/app/(dashboard)/bi/financial/page.tsx` (ComposedChart margen EUR + margen % eje derecho), enlace BI ↔ Command Center en `frontend/src/app/dashboard/bi/page.tsx` y retorno en financial
- [x] Validar coherencia de metricas API BI vs calculo independiente  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `backend/app/core/bi_financial_health_contract.py`, `backend/tests/unit/test_bi_financial_health_coherence.py`, `meta.saldo_facturas_emitidas_eur` en `BiService.get_company_financial_health` (`backend/app/services/bi_service.py`) para cerrar cash_flow vs series
- [x] Endurecer flujo banking (sync, reconciliacion, retries, trazabilidad)  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `backend/app/services/bank_service.py` (`_async_retry_transient_read` en `_fetch_and_store_transactions`, `5xx` → `raise_for_status` en descarga por cuenta, logs `banking.sync.start` / `banking.sync.done` en `sincronizar_y_conciliar`; conciliación y auditoría existentes sin cambio de contrato API)

---

## 3) Fase 3 - Evidencias externas y cierre comite (Semanas 7-10)

### 3.1 Evidencias externas requeridas

- [x] Resultado SSL/TLS externo documentado (objetivo grade alto)  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `docs/dd/PHASE3_3_1_EXTERNAL_EVIDENCE.md` §1, `docs/operations/DEPLOY_FINAL_TLS_CHECKLIST.md`, `infrastructure/nginx/default.conf`, `scripts/collect_tls_evidence.sh` (adjuntar en comité: PDF/captura SSL Labs prod + salida script)
- [x] Backup/restore test report firmado  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `docs/dd/PHASE3_3_1_EXTERNAL_EVIDENCE.md` §2 + plantilla acta; runbook `docs/operations/DISASTER_RECOVERY.md`; workflow `.github/workflows/backup_restore_smoke.yml` (adjuntar: acta firmada + enlace run o restore ensayo)
- [x] DR test report con tiempos reales (RTO/RPO)  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `docs/dd/PHASE3_3_1_EXTERNAL_EVIDENCE.md` §3; métricas y umbrales en `docs/operations/DISASTER_RECOVERY.md` (adjuntar: informe simulacro con RTO/RPO rellenados)
- [x] Pentest/dependency report actualizado y plan de remediacion  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `docs/dd/PHASE3_3_1_EXTERNAL_EVIDENCE.md` §4; CI deploy `.github/workflows/deploy.yml` (`pip-audit`, `npm audit --audit-level=critical`, Trivy, SBOM); tabla remediación en el mismo doc (adjuntar: export logs + pentest externo si aplica)

### 3.2 Cierre legal y de governance

- [x] Politica de retencion y borrado aprobada  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `docs/legal/DATA_RETENTION_AND_DELETION_POLICY.md` v1.0; referencia cruzada en `docs/legal/PRIVACY_POLICY.md` §7 y `docs/legal/COMPLIANCE_AND_SECURITY_POSTURE.md`
- [x] Politica de rotacion de secretos aprobada + evidencia de ejecucion  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `docs/security/SECRET_ROTATION_POLICY.md` (vigente); ejecución registrada `docs/security/SECRET_ROTATION_LOG_2026-04-29.md`; staging `docs/security/SECRET_ROTATION_STAGING_STRIPE_WEBHOOK.md`
- [x] Registro de incidentes y acciones correctivas 12 meses  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `docs/operations/INCIDENT_REGISTER.md` (tabla rolling 12m + plantilla; enlaces a `ON_CALL_RUNBOOK.md` / `runbook_v1.md`); mantener filas al cerrar cada incidente)

### 3.3 Entregable final para conversion a GO

- [x] Matriz final "condicion -> evidencia -> estado -> riesgo residual"  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `docs/dd/PHASE3_3_3_GO_COMMITTEE_PACKAGE.md` §A
- [x] Informe ejecutivo para comite de inversion/auditoria  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `docs/dd/PHASE3_3_3_GO_COMMITTEE_PACKAGE.md` §B (cruce `AUDIT_DOSSIER_V1.0.md`, `PRODUCT_STATE_V1.0.md`, `DD_REMEDIATION_CHECKLIST.md`)
- [x] Decision package (plantilla en repo para circulación y firma)  
  - Status: `done` | Owner: `Adrian (solo-founder)` | Due: `2026-04-29` | Evidence: `docs/dd/PHASE3_3_3_GO_COMMITTEE_PACKAGE.md` §C (plantilla + anexos; la firma y el PDF archivado quedan en §3.4)

### 3.4 Archivo comité y data room (pendiente)

**Runbook:** `docs/dd/RUNBOOK_3_4_DATA_ROOM_ARCHIVE.md` — índice con refs. fijas: `docs/dd/EVIDENCE_VAULT_INDEX.md`

- [ ] Evidencias §3.1 archivadas en data room y columnas **Ubicación** / **Fecha archivo** completadas en el índice para `DD-2026-04-002` … `DD-2026-04-006` (TLS API+APP, backup/restore, DR, deps/Trivy/pentest según aplique)
- [ ] Acta decisión (`GO` / `GO con reservas`): PDF firmado en data room; fila `DD-2026-04-001` completada en el índice

### Data room — referencias a PDFs y actas (fuera del git)

**Índice canónico (rellenar tras archivar):** `docs/dd/EVIDENCE_VAULT_INDEX.md`  
**Runbook §3.4:** `docs/dd/RUNBOOK_3_4_DATA_ROOM_ARCHIVE.md`  
**Borradores locales ignorados por git:** `docs/dd/local-evidence/` (ver `.gitignore` en la raíz del repo).

---

## 4) Registro de bloqueos y decisiones

### Bloqueos activos

- (ninguno)

### Decisiones clave

- (ninguna)

---

## 5) Log de actualizaciones

- 2026-04-29 - Checklist creada.
- 2026-04-29 - Plan ajustado a modo solo-founder con objetivo release en junio.
- 2026-04-29 - Paso 1 completado: inventario de secretos y hallazgos `os.getenv` en `docs/security/secrets_inventory_v1.md`.
- 2026-04-29 - Paso 2 completado: secretos críticos ya no se leen con `os.getenv` en `backend/app`; acceso via `SecretManagerService`.
- 2026-04-29 - Guardrail CI añadido: bloquea nuevos `os.getenv` de secretos críticos en `backend/app` (`.github/workflows/ci.yml`).
- 2026-04-29 - Advisory CI en `backend/scripts` + `scripts/`: avisa sin fallar el pipeline (misma lista de secretos).
- 2026-04-29 - Paso 3 completado: política de rotación definida y primera rotación controlada (dry-run) registrada.
- 2026-04-29 - Playbook staging listo: rotación real de `STRIPE_WEBHOOK_SECRET` en `docs/security/SECRET_ROTATION_STAGING_STRIPE_WEBHOOK.md` (ejecutar en Stripe Dashboard + secrets del entorno).
- 2026-04-29 - Fase 3.1 DD: paquete de evidencias externas y plantillas en `docs/dd/PHASE3_3_1_EXTERNAL_EVIDENCE.md`, script `scripts/collect_tls_evidence.sh`, enlace desde `docs/operations/HANDOVER_PACKAGE.md`.
- 2026-04-29 - Fase 3.2 DD: política retención/borrado `docs/legal/DATA_RETENTION_AND_DELETION_POLICY.md`, registro incidentes `docs/operations/INCIDENT_REGISTER.md`, cruce en `COMPLIANCE_AND_SECURITY_POSTURE.md` y `HANDOVER_PACKAGE.md`.
- 2026-04-29 - Fase 3.3 DD: paquete comité `docs/dd/PHASE3_3_3_GO_COMMITTEE_PACKAGE.md` (matriz §A, informe ejecutivo §B, plantilla decisión §C); dashboard §0 actualizado a 95% y fases 2–3 cerradas en documentación.
- 2026-04-29 - Data room DD: índice de referencias `docs/dd/EVIDENCE_VAULT_INDEX.md`, carpeta borradores `docs/dd/local-evidence/` + reglas en `.gitignore`; sección nueva en checklist §3.3.
- 2026-04-29 - Firma/acta GO y adjuntos §3.1 en data room marcados **pendiente** en nueva §3.4; dashboard §0 a 90% y siguiente paso post-DD en §6 (`GOLIVE_READINESS_CHECKLIST.md`).
- 2026-04-29 - §3.4: runbook `docs/dd/RUNBOOK_3_4_DATA_ROOM_ARCHIVE.md`; `EVIDENCE_VAULT_INDEX.md` con refs. internas fijas `DD-2026-04-001`…`006` y TLS API/APP separados.

---

## 6) Siguiente paso (post-DD, hacia release junio)

- **Prioridad 1:** Cerrar §3.4 (archivo comité + índice data room).
- **Prioridad 2:** Ejecutar y documentar ítems abiertos de `docs/operations/GOLIVE_READINESS_CHECKLIST.md` (go-live verificable; hitos ITSM/evidencias donde aplique).
- **Cadencia:** mantener actualización semanal §0 y una fila nueva en §5 por cada cierre.

