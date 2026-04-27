# Politica BCK-001: backups S3 en region UE y cifrado

## Alcance

Esta politica aplica a los backups generados por:

- `.github/workflows/backup_daily.yml` (`scripts/backup_db.sh`, backup logico Supabase).
- `.github/workflows/backup_restore_smoke.yml` (validacion semanal de restore).
- `infra/backup_system.sh` cuando se usa la ruta de subida directa a Amazon S3.

## Residencia de datos

Los buckets de backup deben residir en una region AWS Europa (`eu-*`). La region operativa se define en el secreto de GitHub Actions `BACKUP_AWS_REGION` y debe coincidir con la ubicacion real del bucket S3. Ejemplos validos:

- `eu-west-1`
- `eu-south-2`
- `eu-central-1`

Los workflows fallan si `BACKUP_AWS_REGION` no empieza por `eu-*`, si el bucket no esta en una region UE, o si la region configurada no coincide con la region real del bucket.

## Cifrado en reposo

Cada upload a S3 fuerza cifrado server-side:

- Por defecto: SSE-S3 (`AES256`).
- Opcional: SSE-KMS (`aws:kms`) si se configura `BACKUP_S3_KMS_KEY_ID`.

Tras subir el backup, el workflow ejecuta `head-object` y falla si el objeto no informa `ServerSideEncryption` como `AES256` o `aws:kms`.

Ademas de la cabecera por objeto, el bucket productivo debe tener default encryption activado y una politica de bucket que deniegue `PutObject` sin cifrado server-side.

## Retencion exacta

La retencion operativa aprobada para backups RGPD/S3 es:

- **S3 productivo (`BACKUP_S3_PREFIX`, default `ab-logistics/daily`): 35 dias naturales** desde la creacion del objeto. La eliminacion se aplica mediante lifecycle rule del bucket sobre el prefijo de backups.
- **Versiones no corrientes S3, si versioning esta activo: 7 dias naturales** desde que dejan de ser version actual. El objetivo es permitir rollback corto sin convertir backups antiguos en retencion indefinida.
- **Multipart uploads incompletos S3: 1 dia natural** desde inicio del multipart upload.
- **Artifacts de GitHub Actions (`supabase-backup`): 2 dias naturales**, definido en `.github/workflows/backup_daily.yml` con `retention-days: 2`.
- **Copias locales del script legacy `infra/backup_system.sh`: 3 dias naturales** por defecto (`RETENTION_DAYS=3`), salvo override documentado en el entorno.

La retencion de 35 dias permite cubrir el RPO diario de 24 horas, ventanas de investigacion y solicitudes de rollback operativo sin conservar copias personales mas alla de lo necesario. Cualquier legal hold, requerimiento fiscal o instruccion contractual que exija mayor conservacion debe documentarse como excepcion aprobada por el owner legal/ops y revisarse al menos trimestralmente.

La configuracion minima de lifecycle esperada en el bucket S3 es:

```json
{
  "Rules": [
    {
      "ID": "ab-logistics-backups-retention-35d",
      "Status": "Enabled",
      "Filter": { "Prefix": "ab-logistics/daily/" },
      "Expiration": { "Days": 35 },
      "NoncurrentVersionExpiration": { "NoncurrentDays": 7 },
      "AbortIncompleteMultipartUpload": { "DaysAfterInitiation": 1 }
    }
  ]
}
```

Si `BACKUP_S3_PREFIX` usa un valor distinto, el `Filter.Prefix` de la lifecycle rule debe coincidir exactamente con ese prefijo terminado en `/`.

## Secretos requeridos

GitHub Actions:

- `SUPABASE_ACCESS_TOKEN`
- `SUPABASE_PROJECT_REF`
- `SUPABASE_DB_PASSWORD`
- `BACKUP_AWS_ACCESS_KEY_ID`
- `BACKUP_AWS_SECRET_ACCESS_KEY`
- `BACKUP_AWS_REGION` con valor `eu-*`
- `BACKUP_S3_BUCKET`
- `BACKUP_S3_PREFIX`
- `BACKUP_S3_KMS_KEY_ID` opcional para SSE-KMS

VPS/script legacy:

- `AWS_S3_BUCKET`
- `AWS_S3_REGION` o `AWS_REGION` con valor `eu-*`
- `AWS_S3_PREFIX`
- `AWS_S3_KMS_KEY_ID` opcional para SSE-KMS

## Validacion automatica (CI / VPS)

El script `scripts/validate_backup_s3_bucket.sh` comprueba en el bucket configurado:

1. **Public Access Block** — las cuatro opciones en `true` (`get-public-access-block`).
2. **Cifrado por defecto** — existe `ServerSideEncryptionConfiguration` en el bucket (`get-bucket-encryption`).
3. **Lifecycle** — al menos una regla `Enabled` con `Expiration.Days == 35` que cubra el prefijo de backups (`BACKUP_S3_PREFIX` / `AWS_S3_PREFIX`, default `ab-logistics/daily/` en Actions).

Se invoca al final de `backup_daily.yml` (tras subir el objeto) y al inicio de `backup_restore_smoke.yml` (antes de descargar), y opcionalmente desde `infra/backup_system.sh` tras un upload AWS correcto.

### Permisos IAM adicionales (clave de backup)

Ademas de `PutObject`, `GetObject`, `ListBucket`, `HeadObject`, la cuenta usada en GitHub Actions debe poder:

- `s3:GetBucketPublicAccessBlock`
- `s3:GetBucketEncryption`
- `s3:GetLifecycleConfiguration`

## Evidencia operativa

La evidencia de cumplimiento de BCK-001 queda en:

- Logs del job `Backup Daily`: region UE validada, region real del bucket validada, objeto cifrado y paso **Validate bucket security**.
- Logs del job `Backup Restore Smoke`: validacion de bucket (PAB/encryption/lifecycle), ultimo backup descargado desde bucket UE y cifrado validado antes del restore.
- Configuracion del bucket en AWS: region `eu-*`, default encryption activo, versioning recomendado y bloqueo de acceso publico.

## Checks operativos

### Diario

- Confirmar que el ultimo workflow `Backup Daily` ha terminado en verde.
- Verificar que el objeto mas reciente existe bajo `BACKUP_S3_PREFIX` y conserva `ServerSideEncryption`.
- Revisar que el timestamp del ultimo backup cumple RPO de 24 horas.
- Si falla el backup, abrir incidente P2; subir a P1 si coincide con migracion, release de base de datos o incidencia de integridad.

### Semanal

- Revisar permisos IAM: acceso limitado a `PutObject`, `GetObject`, `ListBucket` y `HeadObject` sobre bucket/prefix necesario.
- Confirmar que bloqueo de acceso publico, versioning y default encryption siguen activos.
- Confirmar ejecucion verde de `Backup Restore Smoke` o lanzar `workflow_dispatch` manual.
- Guardar evidencia de restore: workflow run, backup usado, region, cifrado, conteo de tablas, validacion RLS y tabla de tiempos medidos del job summary.
- Revisar retencion de artifacts de GitHub Actions: el artifact corto no sustituye al backup S3.

### Mensual

- Revisar lifecycle S3: expiracion de objetos actuales a 35 dias, versiones no corrientes a 7 dias y multipart incompletos a 1 dia.
- Muestrear que no existen objetos bajo `BACKUP_S3_PREFIX` con antiguedad superior a 35 dias salvo legal hold documentado.
- Revisar que `docs/operations/DISASTER_RECOVERY.md` sigue reflejando comandos validos para el entorno actual.

## Runbook ante fallo de backup

1. Identificar paso fallido: secretos, export Supabase, region S3, upload, cifrado o artifact.
2. Si fallan secretos/permisos, rotar o corregir credenciales en GitHub Actions sin exponer valores en logs.
3. Si falla region/cifrado, no desactivar validaciones; corregir bucket, KMS o `BACKUP_AWS_REGION`.
4. Si no hay backup valido en las ultimas 24 horas, registrar riesgo de RPO y notificar a Data/Ops owner.
5. Tras recuperar, ejecutar `Backup Daily` manual y luego `Backup Restore Smoke`.
