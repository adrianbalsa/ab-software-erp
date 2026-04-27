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
8. **`STRIPE_BILLING.md`** + webhooks (`api/v1/webhooks/stripe`) — facturación SaaS.
9. **`health_recovery.md`**, **`REDIS_001_HA_BILLING_QUEUE.md`** — degradación y colas.

## Plantillas de cierre (evidencia fuera del repo público)

- **`HANDOVER_ACTA_TEMPLATE.md`** — acta de sesión / lista de accesos revisados (sin secretos).
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

## Revision documental (sin sustituir acta firmada)

Tras cada handover o cambio de topología, actualizar la sección **«Revisión handover»** al final de `OPS_001_TOPOLOGIA_PLATAFORMA.md` (fecha UTC + responsable).
