#!/usr/bin/env bash
# ─── AB Logistics OS — backup cifrado de Postgres (producción) ───────────────
# Requisitos: pg_dump, openssl 1.1+ (AES-256-CBC + PBKDF2).
# Variables:
#   ENCRYPTION_SECRET_KEY  (obligatoria) — misma clave lógica que el backend Fernet;
#                            aquí se usa como passphrase para openssl (no imprimir).
#   DATABASE_URL           — URI SQLAlchemy o libpq, p. ej. postgresql://… o postgresql+psycopg://…
#   O bien POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB
#   BACKUP_DIR             — destino (default: ./backups)
#   RETENTION_DAYS         — borra *.sql.enc más antiguos (default: 14; 0 = no borrar)
#
# Uso:  ./infra/scripts/backup_db.sh
# Cron: 0 3 * * * cd /opt/ab-logistics && ./infra/scripts/backup_db.sh >> /var/log/backup_db.log 2>&1
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

: "${ENCRYPTION_SECRET_KEY:?Defina ENCRYPTION_SECRET_KEY para cifrar el volcado}"

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"

SQL_TMP="$(mktemp "${TMPDIR:-/tmp}/ab_pg_dump.XXXXXX.sql")"
ENC_OUT="${BACKUP_DIR}/pg_dump_${STAMP}.sql.enc"
OPENSSL_PASS_VAR="BACKUP_OPENSSL_PASS"

cleanup() {
  rm -f "$SQL_TMP"
}
trap cleanup EXIT

# URI compatible con pg_dump (libpq): quitar prefijo +psycopg de SQLAlchemy
build_uri() {
  local uri="${DATABASE_URL:-}"
  if [[ -n "$uri" ]]; then
    uri="${uri//postgresql+psycopg:\/\//postgresql:\/\/}"
    uri="${uri//postgres:\/\//postgresql:\/\/}"
    printf '%s' "$uri"
    return 0
  fi
  local u="${POSTGRES_USER:?POSTGRES_USER o DATABASE_URL}"
  local p="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD o DATABASE_URL}"
  local h="${POSTGRES_HOST:-localhost}"
  local port="${POSTGRES_PORT:-5432}"
  local db="${POSTGRES_DB:?POSTGRES_DB o DATABASE_URL}"
  printf 'postgresql://%s:%s@%s:%s/%s' "$u" "$p" "$h" "$port" "$db"
}

PGURI="$(build_uri)"

echo "[backup_db] Volcando base de datos (${STAMP})…"
if ! command -v pg_dump >/dev/null 2>&1; then
  echo "[backup_db] ERROR: pg_dump no está en PATH (instala postgresql-client)." >&2
  exit 1
fi

pg_dump "$PGURI" \
  --no-owner \
  --no-acl \
  --format=plain \
  --file="$SQL_TMP"

echo "[backup_db] Cifrando con openssl (AES-256-CBC, PBKDF2)…"
# Passphrase vía variable de entorno (no aparece en ps)
export OPENSSL_PASS="${ENCRYPTION_SECRET_KEY}"
if ! openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 \
  -pass env:OPENSSL_PASS \
  -in "$SQL_TMP" \
  -out "$ENC_OUT"; then
  echo "[backup_db] ERROR: cifrado fallido." >&2
  exit 1
fi
unset OPENSSL_PASS

echo "[backup_db] OK: ${ENC_OUT}"

if [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] && [[ "$RETENTION_DAYS" -gt 0 ]]; then
  echo "[backup_db] Purga de backups > ${RETENTION_DAYS} días…"
  find "$BACKUP_DIR" -maxdepth 1 -name 'pg_dump_*.sql.enc' -type f -mtime "+${RETENTION_DAYS}" -print -delete || true
fi
