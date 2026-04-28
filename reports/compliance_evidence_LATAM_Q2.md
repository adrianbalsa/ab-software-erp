# Compliance evidence (sanitized)

- **Generated (UTC):** 2026-04-27T20:47:26Z
- **Scope:** Hito 1.4 password posture + PII trace metadata (aggregates only).
- **Restriction:** No credentials, hashes, or per-subject PII in this file.

## Aggregated database metrics

- `audit_logs_total`: 60
- `clientes_pseudonymized_at_null`: 0
- `clientes_pseudonymized_at_set`: 1
- `clientes_total`: 1
- `usuarios_argon2id`: 1
- `usuarios_legacy_sha256_hex`: 3
- `usuarios_needs_rehash_true`: 3
- `usuarios_password_must_reset_true`: 0
- `usuarios_total`: 4

## Connectivity (deep-health style)

### postgresql
- ok: True
- detail: DATABASE_URL not configured

### redis
- ok: True
- detail: REDIS_URL not configured
- skipped: True

### supabase_rest
- ok: True
- detail: supabase_ok

## S3 backup encryption (configuration probe)

- detail: no_backup_bucket_env
- status: skipped

## Notes

- Object-level SSE for uploads is enforced in GitHub Actions (`backup_daily.yml`).
- Bucket default encryption and lifecycle are validated by `scripts/validate_backup_s3_bucket.sh` in CI.
