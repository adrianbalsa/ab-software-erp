# HANDOVER-001: paquete de transferencia operativa (Fase 3.4)

Objetivo: que un **equipo externo** (platform, SRE o MSP) pueda operar incidencias **P1/P2** sin depender del fundador, usando solo documentación en repo + accesos provisionados fuera del git.

## Orden de lectura recomendado

1. **`OPS_001_TOPOLOGIA_PLATAFORMA.md`** — dominios, Railway/Vercel/Supabase/Redis, variables críticas, checklist OPS.
2. **`ON_CALL_RUNBOOK.md`** — severidades, primeros 15 minutos, matriz runbooks.
3. **`DISASTER_RECOVERY.md`** — restore DB desde backup S3.
4. **`BACKUP_S3_POLICY.md`** — BCK-001, región UE, cifrado.
5. **`VERIFACTU_OPERATIONS_RUNBOOK.md`** — flujo fiscal VeriFactu / AEAT en producción (lectura técnica).
6. **`AEAT_VERIFACTU_HOMOLOGACION.md`** + **`MTLS_CERTIFICATE_RENEWAL.md`** — envíos AEAT y certificados.
7. **`MONITORING_OBSERVABILITY.md`** — `/health/deep`, Sentry, monitores externos.
8. **`GOLIVE_READINESS_CHECKLIST.md`** — guía de secretos (`ALERT_WEBHOOK_URL`) + protocolo CRITICAL + smoke-test webhook.
9. **`STRIPE_BILLING.md`** + webhooks (`api/v1/webhooks/stripe`) — facturación SaaS.
9. **`health_recovery.md`**, **`REDIS_001_HA_BILLING_QUEUE.md`** — degradación y colas.

## Plantillas de cierre (evidencia fuera del repo público)

- **`HANDOVER_ACTA_TEMPLATE.md`** — acta de sesión / lista de accesos revisados (sin secretos).
- **DD Fase 3.1 (SSL, backup/restore, DR, dependencias):** `docs/dd/PHASE3_3_1_EXTERNAL_EVIDENCE.md` + script `scripts/collect_tls_evidence.sh`.
- **DD Fase 3.2 (governance):** retención/borrado `docs/legal/DATA_RETENTION_AND_DELETION_POLICY.md`; incidentes `docs/operations/INCIDENT_REGISTER.md`; rotación secretos `docs/security/SECRET_ROTATION_POLICY.md`.
- **DD Fase 3.3 (decisión GO):** `docs/dd/PHASE3_3_3_GO_COMMITTEE_PACKAGE.md` (matriz, informe ejecutivo, plantilla de firma); índice data room `docs/dd/EVIDENCE_VAULT_INDEX.md`; runbook archivo comité `docs/dd/RUNBOOK_3_4_DATA_ROOM_ARCHIVE.md`; borradores locales `docs/dd/local-evidence/`.
- Evidencias AEAT / compliance: plantillas en `AEAT_HOMOLOGACION_EVIDENCE_TEMPLATE.md`, informes `generate_compliance_report.py` (ver `backend/scripts/README.md`).

## Responsabilidades post-handover

| Área | Owner sugerido | Documento |
|------|------------------|-------------|
| API / worker Railway | | OPS-001 |
| Front Vercel | | OPS-001 |
| Supabase / SQL / RLS | | OPS-001 + DR |
| Redis / cola ARQ | | REDIS_001 |
| VeriFactu / AEAT | | VERIFACTU_OPERATIONS_RUNBOOK + AEAT_* |
| Billing Stripe | | STRIPE_BILLING |
| On-call / escalado | | ON_CALL_RUNBOOK |

## Smoke-test obligatorio post-deploy

Tras cada despliegue inicial (staging/prod), ejecutar:

`POST /api/v1/admin/test-alert`

Criterio de aceptacion:

- mensaje recibido en canal on-call en <60s;
- campos visibles: Entorno, Tenant ID, Timestamp UTC;
- evidencia archivada en acta/ticket de cambio (sin exponer tokens).

## Revision documental (sin sustituir acta firmada)

Tras cada handover o cambio de topología, actualizar la sección **«Revisión handover»** al final de `OPS_001_TOPOLOGIA_PLATAFORMA.md` (fecha UTC + responsable).
