#!/usr/bin/env bash
# AB Logistics OS — Backup físico diario (Postgres + Redis)
#
# Crea un .tar.gz con:
#  - pg_dump (SQL) de producción
#  - Redis dump.rdb (rate limiting + sesiones)
# y lo sube a almacenamiento externo vía rclone o aws-cli.
#
# Requisitos previos en el VPS:
#  - pg_dump / psql disponibles (postgresql-client)
#  - Docker + docker compose (para pedir BGSAVE a Redis si aplica)
#  - rclone configurado o aws-cli configurado
#
# Variables (recomendadas) en .env.prod o en el entorno del shell:
#  - ENV_FILE: ruta al .env.prod (default: ./ .env.prod respecto al repo)
#
# Postgres (pg_dump):
#  - DATABASE_URL (recomendado). Alternativa: POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB y (opcional) POSTGRES_HOST/POSTGRES_PORT
#
# Redis dump.rdb:
#  - REDIS_DUMP_HOST_PATH (default: ./data/redis/dump.rdb)
#  - REDIS_BGSAVE_VIA_DOCKER (default: 1). Si 0, solo copia el dump.rdb existente.
#
# Upload:
#  - RCLONE_REMOTE (p. ej. "myrclone") y RCLONE_DEST (p. ej. "backups/ab-logistics")
#    o
#  - AWS_S3_BUCKET (p. ej. "mi-bucket") y AWS_S3_PREFIX (default: "ab-logistics/backups")
#
# Limpieza:
#  - RETENTION_DAYS (default: 3)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.prod}"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-${ROOT_DIR}/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-3}"

DATE_UTC="$(date -u +%Y%m%d_%H%M%S)"
ARCHIVE_NAME="ablogistics_backup_${DATE_UTC}.tar.gz"
ARCHIVE_PATH="${BACKUP_DIR}/${ARCHIVE_NAME}"

REDIS_DUMP_HOST_PATH="${REDIS_DUMP_HOST_PATH:-${ROOT_DIR}/data/redis/dump.rdb}"
REDIS_BGSAVE_VIA_DOCKER="${REDIS_BGSAVE_VIA_DOCKER:-1}"

mkdir -p "${BACKUP_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[backup_system] ERROR: no existe ENV_FILE: ${ENV_FILE}" >&2
  exit 1
fi

echo "[backup_system] Cargando variables desde ${ENV_FILE}…"
set -a
. "${ENV_FILE}"
set +a

if [[ -z "${DATABASE_URL:-}" ]]; then
  # Fallback: construir DATABASE_URL desde variables POSTGRES_*
  if [[ -n "${POSTGRES_USER:-}" && -n "${POSTGRES_PASSWORD:-}" && -n "${POSTGRES_DB:-}" ]]; then
    POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
    POSTGRES_PORT="${POSTGRES_PORT:-5432}"
    DRIVER="${SQLALCHEMY_DATABASE_DRIVER:-postgresql+psycopg}"
    # driver puede incluir prefijo tipo postgresql+psycopg; pg_dump usa "postgresql"
    DRIVER="${DRIVER%%+*}"
    DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
  else
    echo "[backup_system] ERROR: define DATABASE_URL (recomendado) o POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB en .env.prod" >&2
    exit 1
  fi
fi

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "[backup_system] ERROR: pg_dump no está en PATH. Instala postgresql-client." >&2
  exit 1
fi

if ! command -v tar >/dev/null 2>&1; then
  echo "[backup_system] ERROR: tar no está disponible." >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

PG_DUMP_OUT="${TMP_DIR}/pg_dump.sql"
REDIS_OUT="${TMP_DIR}/dump.rdb"

echo "[backup_system] 1/3 pg_dump (${DATE_UTC})…"
#
# Nota:
# - pg_dump genera SQL plain para restauración con psql.
# - Usamos --no-owner/--no-acl para evitar dependencias de roles/ACLs.
# - Si tu DATABASE_URL requiere SSL, ponlo ya en DATABASE_URL.
#
pg_dump "${DATABASE_URL}" \
  --no-owner \
  --no-acl \
  --format=plain \
  --file="${PG_DUMP_OUT}"

echo "[backup_system] 2/3 Redis dump.rdb…"
if [[ "${REDIS_BGSAVE_VIA_DOCKER}" == "1" ]]; then
  if [[ ! -f "${COMPOSE_FILE}" ]]; then
    echo "[backup_system] ERROR: no existe ${COMPOSE_FILE}" >&2
    exit 1
  fi

  # Pide snapshot (BGSAVE). Luego copiamos dump.rdb desde el volumen host.
  # lastsave devuelve epoch seconds.
  LASTSAVE_BEFORE="$(
    docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T redis \
      redis-cli lastsave 2>/dev/null || true
  )"

  docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T redis redis-cli bgsave >/dev/null

  # Espera hasta que lastsave cambie o timeout.
  for _ in $(seq 1 30); do
    LASTSAVE_AFTER="$(
      docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T redis \
        redis-cli lastsave 2>/dev/null || true
    )"
    if [[ -n "${LASTSAVE_BEFORE}" && -n "${LASTSAVE_AFTER}" && "${LASTSAVE_AFTER}" != "${LASTSAVE_BEFORE}" ]]; then
      break
    fi
    sleep 1
  done
fi

if [[ ! -f "${REDIS_DUMP_HOST_PATH}" ]]; then
  echo "[backup_system] ERROR: no existe dump.rdb en ${REDIS_DUMP_HOST_PATH}" >&2
  exit 1
fi

cp -f "${REDIS_DUMP_HOST_PATH}" "${REDIS_OUT}"

echo "[backup_system] 3/3 Empaquetando → ${ARCHIVE_PATH}…"
tar -C "${TMP_DIR}" -czf "${ARCHIVE_PATH}" "pg_dump.sql" "dump.rdb"

echo "[backup_system] Subida a almacenamiento externo…"
UPLOADED=0

if [[ -n "${RCLONE_REMOTE:-}" && -n "${RCLONE_DEST:-}" ]]; then
  if ! command -v rclone >/dev/null 2>&1; then
    echo "[backup_system] ERROR: rclone no está instalado." >&2
    exit 1
  fi
  rclone copyto "${ARCHIVE_PATH}" "${RCLONE_REMOTE}:${RCLONE_DEST}/${ARCHIVE_NAME}" --s3-chunk-size 64M
  UPLOADED=1
fi

if [[ "${UPLOADED}" -eq 0 && -n "${AWS_S3_BUCKET:-}" ]]; then
  if ! command -v aws >/dev/null 2>&1; then
    echo "[backup_system] ERROR: aws-cli no está instalado." >&2
    exit 1
  fi
  AWS_S3_PREFIX="${AWS_S3_PREFIX:-ab-logistics/backups}"
  aws s3 cp "${ARCHIVE_PATH}" "s3://${AWS_S3_BUCKET}/${AWS_S3_PREFIX}/${ARCHIVE_NAME}"
  UPLOADED=1
fi

if [[ "${UPLOADED}" -eq 0 ]]; then
  echo "[backup_system] ERROR: configura RCLONE_REMOTE + RCLONE_DEST o AWS_S3_BUCKET (+ opcional AWS_S3_PREFIX)." >&2
  exit 1
fi

echo "[backup_system] OK: ${ARCHIVE_NAME}"

echo "[backup_system] Limpieza: borrar copias locales > ${RETENTION_DAYS} días…"
if [[ "${RETENTION_DAYS}" =~ ^[0-9]+$ ]]; then
  find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'ablogistics_backup_*.tar.gz' -mtime "+${RETENTION_DAYS}" -print -delete || true
fi

