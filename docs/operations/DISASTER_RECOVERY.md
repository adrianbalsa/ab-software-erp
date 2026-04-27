# Disaster Recovery — Restauración DB desde cero

Contexto handover: indice general en **`docs/operations/HANDOVER_PACKAGE.md`**.

Este runbook asume que el backup fue generado por `scripts/backup_db.sh` y contiene:

- `schema.sql` (roles, extensiones, tablas, funciones, políticas)
- `public_data.sql` (datos del esquema `public`)

Variables esperadas:

- `BACKUP_AWS_REGION` (debe ser `eu-*` y coincidir con la región real del bucket)
- `BACKUP_S3_BUCKET`
- `BACKUP_S3_PREFIX`
- `BACKUP_FILE`
- `DATABASE_URL`

La política BCK-001 de residencia UE y cifrado S3 está en `docs/operations/BACKUP_S3_POLICY.md`. La comprobacion automatica de bucket (PAB, cifrado por defecto, lifecycle 35d) esta en `scripts/validate_backup_s3_bucket.sh` (tambien ejecutada en CI).

## Antes de empezar

- Declarar incidente y owner de restauración.
- Congelar escrituras sobre el entorno afectado si hay riesgo de corrupción o doble escritura.
- Confirmar que `BACKUP_FILE` apunta a un backup cifrado, en región UE y dentro del RPO aceptado.
- Validar que se restaura sobre una base nueva o explícitamente autorizada; no sobrescribir producción sin aprobación del incident commander.
- Tener a mano variables, permisos y acceso a GitHub Actions, Supabase/Railway, AWS S3 y DNS si aplica.

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

- Workflow de smoke restore semanal: `.github/workflows/backup_restore_smoke.yml`.
- También se puede ejecutar manualmente desde GitHub Actions (`workflow_dispatch`).
- El workflow publica en el job summary los tiempos medidos por fase: descarga S3, extracción, aplicación de SQL e integridad.

## Tiempos medidos y evidencia

El restore smoke debe conservar la tabla de tiempos del job summary como evidencia operativa. La medición mínima exigida por ejecución es:

| Fase medida | Fuente | Evidencia requerida |
|-------------|--------|---------------------|
| Descarga del último objeto cifrado desde S3 | `RESTORE_DOWNLOAD_SECONDS` | URI S3, región UE y cifrado `AES256` o `aws:kms`. |
| Extracción y validación de layout | `RESTORE_EXTRACT_SECONDS` | Presencia de `schema.sql` y `public_data.sql`. |
| Aplicación de esquema y datos | `RESTORE_APPLY_SECONDS` | `psql -v ON_ERROR_STOP=1` sin errores. |
| Checks de integridad | `RESTORE_INTEGRITY_SECONDS` | Conteo mínimo de tablas, datos de auditoría y RLS activo. |

Para un restore real, el incident commander debe registrar en el ticket:

| Métrica | Cómo se mide | Umbral operativo |
|---------|--------------|------------------|
| RPO real | Hora del incidente menos timestamp del backup restaurado. | <= 24 horas salvo excepción documentada. |
| RTO real | Desde activación formal del procedimiento hasta servicio mínimo validado. | <= 24 horas para restore DB desde S3. |
| Tiempo técnico de restore | Suma de descarga, extracción, aplicación SQL e integridad. | Debe compararse contra el último smoke semanal. |
| Tiempo de validación funcional | Desde final de integridad DB hasta login/dashboard/facturas verificados. | Registrar desviaciones y bloqueos externos. |

Plantilla de registro:

```text
Workflow run:
Backup restaurado:
Region S3:
Cifrado:
RESTORE_DOWNLOAD_SECONDS:
RESTORE_EXTRACT_SECONDS:
RESTORE_APPLY_SECONDS:
RESTORE_INTEGRITY_SECONDS:
Inicio incidente:
Inicio restore:
Fin restore tecnico:
Fin validacion funcional:
RPO real:
RTO real:
Desviaciones:
```

## Verificación post-restore

- `schema.sql` y `public_data.sql` aplicados sin errores (`ON_ERROR_STOP=1`).
- Tablas críticas presentes: `facturas_emitidas`, `clientes`, `flota`, `audit_logs`.
- RLS activo en tablas multi-tenant críticas.
- Login, dashboard y lectura de facturas funcionan contra el entorno restaurado.
- `/live`, `/health` y `/health/deep` vuelven a estado esperado.
- Redis/worker conectan al entorno restaurado solo tras confirmar consistencia de datos.
- Se documenta el backup usado, hora de inicio/fin, RPO real, RTO real y desviaciones.

## Checklist de cierre DR

- [ ] Escrituras reabiertas de forma controlada.
- [ ] Smoke funcional completado con usuario de prueba.
- [ ] Auditoria e integridad VeriFactu revisadas antes de reintentar envios AEAT.
- [ ] Backups reactivados y primer backup post-restore validado.
- [ ] Clientes afectados comunicados segun severidad contractual.
- [ ] Postmortem creado con causa raiz, impacto y acciones preventivas.
