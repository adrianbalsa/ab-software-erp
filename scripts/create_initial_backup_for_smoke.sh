#!/usr/bin/env bash

set -euo pipefail

# Crea un backup inicial compatible con .github/workflows/backup_restore_smoke.yml
# y lo sube cifrado a S3 bajo el prefijo indicado.
#
# Requisitos:
# - pg_dump (cliente PostgreSQL)
# - aws cli autenticado
#
# Variables obligatorias:
# - DATABASE_URL
# - BACKUP_S3_BUCKET
# - BACKUP_S3_PREFIX
# - BACKUP_AWS_REGION (eu-*)
#
# Variables opcionales:
# - BACKUP_WORKDIR (default: /tmp/ab-initial-backup)

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[create_initial_backup_for_smoke] ERROR: comando requerido no encontrado: $cmd" >&2
    exit 1
  fi
}

require_env() {
  local var="$1"
  if [[ -z "${!var:-}" ]]; then
    echo "[create_initial_backup_for_smoke] ERROR: variable requerida vacía: $var" >&2
    exit 1
  fi
}

require_cmd pg_dump
require_cmd aws

require_env DATABASE_URL
require_env BACKUP_S3_BUCKET
require_env BACKUP_S3_PREFIX
require_env BACKUP_AWS_REGION

if [[ "${BACKUP_AWS_REGION}" != eu-* ]]; then
  echo "[create_initial_backup_for_smoke] ERROR: BACKUP_AWS_REGION debe ser eu-* (actual: ${BACKUP_AWS_REGION})" >&2
  exit 1
fi

WORKDIR="${BACKUP_WORKDIR:-/tmp/ab-initial-backup}"
mkdir -p "${WORKDIR}"

TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
ARCHIVE_NAME="supabase_backup_${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="${WORKDIR}/${ARCHIVE_NAME}"
SCHEMA_PATH="${WORKDIR}/schema.sql"
DATA_PATH="${WORKDIR}/public_data.sql"

echo "[create_initial_backup_for_smoke] 1/6 Exportando schema..."
pg_dump "${DATABASE_URL}" \
  --schema-only \
  --no-owner \
  --no-privileges \
  > "${SCHEMA_PATH}"

echo "[create_initial_backup_for_smoke] 2/6 Exportando datos public..."
pg_dump "${DATABASE_URL}" \
  --data-only \
  --schema=public \
  --inserts \
  --no-owner \
  --no-privileges \
  > "${DATA_PATH}"

echo "[create_initial_backup_for_smoke] 3/6 Empaquetando..."
tar -czf "${ARCHIVE_PATH}" -C "${WORKDIR}" schema.sql public_data.sql

echo "[create_initial_backup_for_smoke] 4/6 Subiendo a S3 con SSE..."
aws s3 cp "${ARCHIVE_PATH}" \
  "s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX%/}/${ARCHIVE_NAME}" \
  --region "${BACKUP_AWS_REGION}" \
  --sse AES256

echo "[create_initial_backup_for_smoke] 5/6 Verificando presencia en bucket..."
aws s3 ls "s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX%/}/" --region "${BACKUP_AWS_REGION}" \
  | awk '{print $4}' \
  | grep -E '^supabase_backup_.*\.tar\.gz$' >/dev/null

echo "[create_initial_backup_for_smoke] 6/6 Verificando cifrado del objeto..."
SSE="$(aws s3api head-object \
  --bucket "${BACKUP_S3_BUCKET}" \
  --key "${BACKUP_S3_PREFIX%/}/${ARCHIVE_NAME}" \
  --region "${BACKUP_AWS_REGION}" \
  --query 'ServerSideEncryption' \
  --output text)"

case "${SSE}" in
  AES256|aws:kms) ;;
  *)
    echo "[create_initial_backup_for_smoke] ERROR: cifrado inválido en objeto (${SSE})." >&2
    exit 1
    ;;
esac

echo
echo "[create_initial_backup_for_smoke] OK"
echo "  Archivo local: ${ARCHIVE_PATH}"
echo "  Objeto S3: s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX%/}/${ARCHIVE_NAME}"
echo "  SSE: ${SSE}"
echo
echo "Siguiente paso: relanzar GitHub Action 'Backup Restore Smoke'."

