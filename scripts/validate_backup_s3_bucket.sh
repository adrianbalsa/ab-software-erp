#!/usr/bin/env bash
# BCK-001 — Valida postura de seguridad del bucket de backups (PAB, cifrado por defecto, lifecycle 35d).
# Uso: credenciales AWS ya configuradas (p. ej. tras configure-aws-credentials en GitHub Actions).
#
# Variables:
#   BACKUP_S3_BUCKET o AWS_S3_BUCKET (obligatorio)
#   BACKUP_S3_PREFIX o AWS_S3_PREFIX (opcional, default ab-logistics/daily)
#   BACKUP_LIFECYCLE_EXPIRATION_DAYS (opcional, default 35)
#
set -euo pipefail

BUCKET="${BACKUP_S3_BUCKET:-${AWS_S3_BUCKET:-}}"
PREFIX="${BACKUP_S3_PREFIX:-${AWS_S3_PREFIX:-ab-logistics/daily}}"
EXPIRE_DAYS="${BACKUP_LIFECYCLE_EXPIRATION_DAYS:-35}"

if [[ -z "${BUCKET}" ]]; then
  echo "[validate_backup_s3_bucket] ERROR: define BACKUP_S3_BUCKET o AWS_S3_BUCKET" >&2
  exit 1
fi

# Prefijo de objetos de backup: siempre termina en /
if [[ "${PREFIX}" != */ ]]; then
  PREFIX="${PREFIX}/"
fi

echo "[validate_backup_s3_bucket] bucket=${BUCKET} backup_prefix=${PREFIX} expected_expiration_days=${EXPIRE_DAYS}"

# --- Public Access Block (las cuatro en true) ---
pab_json="$(aws s3api get-public-access-block --bucket "${BUCKET}" --output json)"
if ! echo "${pab_json}" | jq -e '
  .PublicAccessBlockConfiguration
  | (.BlockPublicAcls == true)
    and (.IgnorePublicAcls == true)
    and (.BlockPublicPolicy == true)
    and (.RestrictPublicBuckets == true)
' >/dev/null; then
  echo "[validate_backup_s3_bucket] ERROR: PublicAccessBlockConfiguration incompleto o desactivado" >&2
  echo "${pab_json}" >&2
  exit 1
fi
echo "[validate_backup_s3_bucket] OK Public Access Block (4/4)"

# --- Cifrado por defecto en bucket ---
enc_json="$(aws s3api get-bucket-encryption --bucket "${BUCKET}" --output json)"
if ! echo "${enc_json}" | jq -e '.ServerSideEncryptionConfiguration.Rules | length >= 1' >/dev/null; then
  echo "[validate_backup_s3_bucket] ERROR: bucket sin ServerSideEncryptionConfiguration.Rules" >&2
  echo "${enc_json}" >&2
  exit 1
fi
echo "[validate_backup_s3_bucket] OK default bucket encryption"

# --- Lifecycle: regla habilitada con expiracion EXPIRE_DAYS que cubre el prefijo de backups ---
lc_json="$(aws s3api get-bucket-lifecycle-configuration --bucket "${BUCKET}" --output json)"

export LC_JSON="${lc_json}"
export BACKUP_PREFIX_NORM="${PREFIX}"
export EXPIRE_DAYS

if ! python3 <<'PY'
import json
import os

cfg = json.loads(os.environ["LC_JSON"])
prefix = os.environ["BACKUP_PREFIX_NORM"]
want_days = int(os.environ["EXPIRE_DAYS"])


def rule_filter_prefix(rule: dict) -> str:
    if "Prefix" in rule and rule["Prefix"]:
        return str(rule["Prefix"])
    filt = rule.get("Filter") or {}
    if isinstance(filt, dict):
        if "Prefix" in filt and filt["Prefix"]:
            return str(filt["Prefix"])
        and_block = filt.get("And")
        if isinstance(and_block, dict) and and_block.get("Prefix"):
            return str(and_block["Prefix"])
    return ""


def prefix_covered_by_rule(backup_prefix: str, rule_prefix: str) -> bool:
    if not rule_prefix:
        return True
    rp = rule_prefix.rstrip("/") + "/"
    bp = backup_prefix if backup_prefix.endswith("/") else backup_prefix + "/"
    return bp.startswith(rp) or rp.startswith(bp.rstrip("/") + "/")


ok = False
for rule in cfg.get("Rules") or []:
    if str(rule.get("Status") or "").strip() != "Enabled":
        continue
    exp = rule.get("Expiration") or {}
    days = exp.get("Days")
    if days is None:
        continue
    if int(days) != want_days:
        continue
    fp = rule_filter_prefix(rule)
    if prefix_covered_by_rule(prefix, fp):
        ok = True
        break

if not ok:
    raise SystemExit(
        f"No enabled lifecycle rule with Expiration.Days=={want_days} covering backup prefix {prefix!r}"
    )
PY
then
  echo "[validate_backup_s3_bucket] ERROR: lifecycle 35d no aplicable al prefijo de backups" >&2
  echo "${lc_json}" >&2
  exit 1
fi
echo "[validate_backup_s3_bucket] OK lifecycle (Expiration.Days=${EXPIRE_DAYS} cubre prefijo)"

echo "[validate_backup_s3_bucket] OK — bucket cumple BCK-001 (PAB + encryption + lifecycle)"
