#!/usr/bin/env bash

set -euo pipefail

# AB Logistics OS — Backup lógico Supabase
# - Dump 1: esquema (roles, extensiones, tablas, políticas, funciones)
# - Dump 2: datos (solo esquema public)
# - Salida: .tar.gz con timestamp UTC

if ! command -v supabase >/dev/null 2>&1; then
  echo "[backup_db] ERROR: supabase CLI no está en PATH." >&2
  exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ab-supabase-backup.XXXXXX")"

cleanup() {
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

mkdir -p "${BACKUP_DIR}"

SCHEMA_SQL="${WORK_DIR}/schema.sql"
DATA_SQL="${WORK_DIR}/public_data.sql"
MANIFEST_TXT="${WORK_DIR}/MANIFEST.txt"
ARCHIVE_PATH="${BACKUP_DIR}/supabase_backup_${TIMESTAMP}.tar.gz"

PROJECT_REF="${SUPABASE_PROJECT_REF:-}"
DB_PASSWORD="${SUPABASE_DB_PASSWORD:-}"

if [[ -n "${PROJECT_REF}" && -n "${DB_PASSWORD}" ]]; then
  echo "[backup_db] Linking Supabase project ${PROJECT_REF}..."
  supabase link --project-ref "${PROJECT_REF}" --password "${DB_PASSWORD}" >/dev/null
fi

echo "[backup_db] Dumping schema..."
supabase db dump --linked --schema public,auth,extensions --file "${SCHEMA_SQL}"

echo "[backup_db] Dumping public data..."
supabase db dump --linked --data-only --schema public --file "${DATA_SQL}"

cat > "${MANIFEST_TXT}" <<EOF
backup_type=supabase_db_dump
generated_at_utc=${TIMESTAMP}
schema_file=$(basename "${SCHEMA_SQL}")
data_file=$(basename "${DATA_SQL}")
EOF

echo "[backup_db] Creating archive ${ARCHIVE_PATH}..."
tar -C "${WORK_DIR}" -czf "${ARCHIVE_PATH}" \
  "$(basename "${SCHEMA_SQL}")" \
  "$(basename "${DATA_SQL}")" \
  "$(basename "${MANIFEST_TXT}")"

echo "[backup_db] OK: ${ARCHIVE_PATH}"
