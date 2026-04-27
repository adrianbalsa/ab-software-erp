# Scripts operativos (backend)

## Informes de cumplimiento (M&A / auditoría)

Los scripts `compliance_mark.py` y `generate_compliance_report.py` son la **base documental** para demostrar, sin PII ni secretos en el artefacto generado:

- Postura de contraseñas (Argon2id / `needs_rehash`) y metadatos agregados de trazabilidad PII (`pseudonymized_at`).
- Conectividad alineada con producción: Supabase REST, Postgres (`DATABASE_URL`), **Redis (`REDIS_URL` resuelto vía `get_settings()`, igual que la app y ARQ)**.
- **S3 de backups** (`BACKUP_S3_BUCKET`): región esperada (`BACKUP_EXPECTED_S3_REGION` o por defecto `eu-west-1` si no se define otra vía `BACKUP_AWS_REGION` / `AWS_REGION`), bloqueo de acceso público (Public Access Block) y cifrado por defecto del bucket (**AES256**).

### Cuándo ejecutarlos

1. **Antes de cada despliegue a staging o producción** (o en CI previo al promote), con las mismas variables que el runtime (sin commitear `.env`).
2. Tras aplicar migraciones Supabase relacionadas con cumplimiento (hito 1.4, cuotas, VeriFactu, etc.).
3. Para archivar evidencia en ticket ITSM / data room M&A: el markdown generado debe vivir fuera del repo o en almacenamiento controlado (muchas rutas `reports/` están en `.gitignore`).

### Ejemplo

```bash
cd backend
python scripts/compliance_mark.py --dry-run
python scripts/generate_compliance_report.py --out reports/compliance_evidence_LATAM_Q2.md
```

Variables típicas para un informe **sin “skipped”** en S3/Redis:

- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (o `SUPABASE_SERVICE_KEY`)
- `DATABASE_URL` (opcional para el ping Postgres en el mismo proceso)
- `REDIS_URL` (misma que workers / rate limit cuando Redis está activo)
- `BACKUP_S3_BUCKET` y credenciales AWS (rol IAM en el entorno **o** `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`, con `BACKUP_AWS_REGION` / `AWS_REGION` coherente con el bucket)

### VeriFactu en producción

Con `ENVIRONMENT=production` y `AEAT_VERIFACTU_ENABLED=true`, la API **no arranca** si no puede resolver el hash génesis VeriFactu vía Secret Manager (`VERIFACTU_GENESIS_HASH` / `VERIFACTU_GENESIS_HASHES` o secretos equivalentes). El envío a la AEAT también valida el génesis por `empresa_id` antes de continuar.

### Go-live salud HTTP (Fase 3.3 — `/health/deep`)

```bash
cd backend
python scripts/check_golive_readiness.py --base-url https://api.<dominio> --strict
python scripts/check_golive_readiness.py --base-url https://api.<dominio> --summarize-deep
```

Guía de monitoreo (Better Stack, Sentry, simulacros): `docs/operations/MONITORING_OBSERVABILITY.md`.

### Handover / Fase 3.4

Índice de documentación para equipo externo y plantilla de acta: `docs/operations/HANDOVER_PACKAGE.md`, `HANDOVER_ACTA_TEMPLATE.md`, `VERIFACTU_OPERATIONS_RUNBOOK.md`.

### Despliegue final TLS / CORS / Redis (Fase 3.2 — solo config)

Sin llamadas de red; valida `ALLOWED_HOSTS`, orígenes CORS y esquema `rediss://` cuando aplica:

```bash
cd backend
PYTHONPATH=. python scripts/check_deploy_infra_readiness.py
PYTHONPATH=. python scripts/check_deploy_infra_readiness.py --strict
```

Checklist operativo (DNS, `openssl`, `curl`, Redis): `docs/operations/DEPLOY_FINAL_TLS_CHECKLIST.md`.

### Homologación AEAT (Fase 3.1 — prerequisitos locales)

Sin llamar a la AEAT, valida flags, URL de pruebas y rutas de certificado mTLS:

```bash
cd backend
PYTHONPATH=. python scripts/check_aeat_homologacion_readiness.py
```

Plantilla para archivar evidencia tras un envío real: `docs/operations/AEAT_HOMOLOGACION_EVIDENCE_TEMPLATE.md`. Procedimiento completo: `docs/operations/AEAT_VERIFACTU_HOMOLOGACION.md`.
