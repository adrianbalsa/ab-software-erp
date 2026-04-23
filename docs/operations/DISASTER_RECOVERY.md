# Disaster Recovery — Restauración DB desde cero

Este runbook asume que el backup fue generado por `scripts/backup_db.sh` y contiene:

- `schema.sql` (roles, extensiones, tablas, funciones, políticas)
- `public_data.sql` (datos del esquema `public`)

Variables esperadas:

- `BACKUP_S3_BUCKET`
- `BACKUP_S3_PREFIX`
- `BACKUP_FILE`
- `DATABASE_URL`

## 5 comandos exactos

```bash
aws s3 cp "s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}/${BACKUP_FILE}" "./${BACKUP_FILE}"
```

```bash
mkdir -p ./restore_db && tar -xzf "./${BACKUP_FILE}" -C ./restore_db
```

```bash
createdb "$(python - <<'PY'
from urllib.parse import urlparse
import os
print(urlparse(os.environ["DATABASE_URL"]).path.lstrip("/"))
PY
)"
```

```bash
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f ./restore_db/schema.sql
```

```bash
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f ./restore_db/public_data.sql
```

## Verificación automática

- Workflow de smoke restore mensual: `.github/workflows/backup_restore_smoke.yml`.
- También se puede ejecutar manualmente desde GitHub Actions (`workflow_dispatch`).
