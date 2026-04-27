#!/usr/bin/env python3
"""
Genera informe M&A sanitizado (sin credenciales ni filas de clientes).

Incluye:
  - Timestamp UTC
  - Conteos agregados vía RPC ``compliance_hito_14_stats``
  - Comprobaciones tipo /health/deep: Supabase REST, Postgres SELECT 1, Redis ping (si configurado)
  - Sondado S3 (boto3): bucket BACKUP_S3_BUCKET, región esperada, PublicAccessBlock, SSE AES256
  - Redis: misma REDIS_URL que ``get_settings()`` (persistencia vía INFO)

  python backend/scripts/generate_compliance_report.py --out backend/reports/compliance_evidence_LATAM_Q2.md
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for env_path in (ROOT / ".env", REPO / ".env"):
    if env_path.exists():
        load_dotenv(env_path)

REPORTS_DIR = ROOT / "reports"


def _s3_backup_compliance_probe() -> dict[str, str]:
    """
    Sonda real AWS S3 (boto3) sobre ``BACKUP_S3_BUCKET`` (fallback ``AWS_S3_BUCKET``).

    Comprueba: región del bucket vs esperada (``BACKUP_EXPECTED_S3_REGION`` o ``eu-west-1`` por
    defecto si no se define otra), PublicAccessBlockConfiguration (las cuatro en True),
    ``ServerSideEncryptionConfiguration`` con algoritmo **AES256**.

    Credenciales: cadena por defecto de boto3 (rol IAM, profile, etc.) o claves explícitas
    ``BACKUP_AWS_*`` / ``AWS_*``. Si faltan datos imprescindibles, ``missing_env`` enumera
    variables concretas (nunca valores).
    """
    bucket = (os.getenv("BACKUP_S3_BUCKET") or os.getenv("AWS_S3_BUCKET") or "").strip()
    if not bucket:
        return {
            "status": "not_configured",
            "missing_env": "BACKUP_S3_BUCKET",
            "hint": "Opcionalmente_AWS_S3_BUCKET_como_alias",
        }

    expected_region = (
        (os.getenv("BACKUP_EXPECTED_S3_REGION") or "").strip()
        or (os.getenv("BACKUP_AWS_REGION") or "").strip()
        or (os.getenv("AWS_S3_REGION") or "").strip()
        or (os.getenv("AWS_REGION") or "").strip()
        or "eu-west-1"
    )

    key_id = (os.getenv("BACKUP_AWS_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID") or "").strip()
    secret = (os.getenv("BACKUP_AWS_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip()
    session_token = (os.getenv("BACKUP_AWS_SESSION_TOKEN") or os.getenv("AWS_SESSION_TOKEN") or "").strip()

    region_for_client = (
        (os.getenv("BACKUP_AWS_REGION") or "").strip()
        or (os.getenv("AWS_S3_REGION") or "").strip()
        or (os.getenv("AWS_REGION") or "").strip()
        or expected_region
    )

    missing: list[str] = []
    if key_id and not secret:
        missing.append("BACKUP_AWS_SECRET_ACCESS_KEY(o_AWS_SECRET_ACCESS_KEY)")
    if secret and not key_id:
        missing.append("BACKUP_AWS_ACCESS_KEY_ID(o_AWS_ACCESS_KEY_ID)")
    if missing:
        return {
            "status": "not_configured",
            "bucket": bucket,
            "expected_region": expected_region,
            "missing_env": ",".join(missing),
        }

    import boto3  # noqa: PLC0415
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError  # noqa: PLC0415

    try:
        session_kw: dict[str, str] = {}
        if key_id and secret:
            session_kw["aws_access_key_id"] = key_id
            session_kw["aws_secret_access_key"] = secret
            if session_token:
                session_kw["aws_session_token"] = session_token

        sess = boto3.session.Session(region_name=region_for_client, **session_kw)
        s3 = sess.client("s3", region_name=region_for_client)
        try:
            s3.head_bucket(Bucket=bucket)
        except NoCredentialsError:
            return {
                "status": "not_configured",
                "bucket": bucket,
                "expected_region": expected_region,
                "missing_env": (
                    "credenciales_AWS:no_hay_rol_IAM_ní_AWS_ACCESS_KEY_ID+AWS_SECRET_ACCESS_KEY"
                    "(ni_variantes_BACKUP_AWS_*)"
                ),
            }
    except NoCredentialsError:
        return {
            "status": "not_configured",
            "bucket": bucket,
            "expected_region": expected_region,
            "missing_env": (
                "credenciales_AWS:no_hay_rol_IAM_ní_AWS_ACCESS_KEY_ID+AWS_SECRET_ACCESS_KEY"
                "(ni_variantes_BACKUP_AWS_*)"
            ),
        }
    except Exception as exc:
        return {"status": "error", "bucket": bucket, "detail": type(exc).__name__}

    out: dict[str, str] = {
        "status": "ok",
        "bucket": bucket,
        "expected_region": expected_region,
        "client_region": region_for_client,
    }

    try:
        loc = s3.get_bucket_location(Bucket=bucket)
        actual = loc.get("LocationConstraint") or "us-east-1"
        out["bucket_actual_region"] = str(actual)
        match = actual == expected_region
        out["region_match"] = str(match).lower()
        if not match:
            out["status"] = "degraded"
            out["region_detail"] = f"expected_{expected_region}_actual_{actual}"
    except (ClientError, BotoCoreError) as exc:
        out["status"] = "error"
        out["location_error"] = type(exc).__name__

    pab_keys = (
        "BlockPublicAcls",
        "IgnorePublicAcls",
        "BlockPublicPolicy",
        "RestrictPublicBuckets",
    )
    try:
        pab = s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"]
        ok_all = all(bool(pab.get(k)) for k in pab_keys)
        out["public_access_block_all_true"] = str(ok_all).lower()
        for k in pab_keys:
            out[f"pab_{k}"] = str(bool(pab.get(k))).lower()
        if not ok_all and out["status"] == "ok":
            out["status"] = "degraded"
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "NoSuchPublicAccessBlockConfiguration":
            out["public_access_block"] = "missing_bucket_has_no_pab"
            if out["status"] == "ok":
                out["status"] = "degraded"
        else:
            out["pab_error"] = code or type(exc).__name__
            out["status"] = "error"

    try:
        enc = s3.get_bucket_encryption(Bucket=bucket)
        rules = enc.get("ServerSideEncryptionConfiguration", {}).get("Rules") or []
        algo = (
            (rules[0].get("ApplyServerSideEncryptionByDefault") or {}).get("SSEAlgorithm")
            if rules
            else None
        )
        out["sse_algorithm"] = str(algo or "none")
        if algo == "AES256":
            out["sse_aes256_default"] = "true"
        else:
            out["sse_aes256_default"] = "false"
            if algo == "aws:kms":
                out["sse_note"] = "default_is_aws_kms_not_aes256"
            if out["status"] == "ok":
                out["status"] = "degraded"
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "ServerSideEncryptionConfigurationNotFoundError":
            out["sse_algorithm"] = "none"
            out["sse_aes256_default"] = "false"
            if out["status"] == "ok":
                out["status"] = "degraded"
        else:
            out["encryption_error"] = code or type(exc).__name__
            out["status"] = "error"

    return out


async def _gather_health() -> dict[str, dict[str, str]]:
    from app.core.config import get_settings  # noqa: PLC0415
    from app.core.health_checks import (  # noqa: PLC0415
        check_postgresql_select_one,
        check_redis_connectivity_for_compliance_report,
        check_supabase_rest,
    )

    settings = get_settings()
    url = (settings.SUPABASE_URL or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or "").strip()

    out: dict[str, dict[str, str]] = {}

    if url and key:
        ok, detail = await check_supabase_rest(url, key)
        out["supabase_rest"] = {"ok": str(ok), "detail": detail}
    else:
        out["supabase_rest"] = {"ok": "skipped", "detail": "missing_url_or_service_key"}

    pg = await check_postgresql_select_one()
    out["postgresql"] = {"ok": str(pg.get("ok")), "detail": str(pg.get("detail", ""))}

    out["redis"] = await check_redis_connectivity_for_compliance_report()
    return out


async def _stats_block() -> dict[str, object]:
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    if not url or not key:
        return {"error": "missing_supabase_for_stats"}
    from supabase import create_client  # noqa: PLC0415

    client = create_client(url, key)
    try:
        res = client.rpc("compliance_hito_14_stats", {}).execute()
    except Exception as exc:
        return {"error": f"rpc_compliance_hito_14_stats:{type(exc).__name__}"}
    data = getattr(res, "data", None)
    return data if isinstance(data, dict) else {}


def _render_md(
    *,
    stats: dict[str, object],
    health: dict[str, dict[str, str]],
    s3: dict[str, str],
) -> str:
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# Compliance evidence (sanitized)",
        "",
        f"- **Generated (UTC):** {ts}",
        "- **Scope:** Hito 1.4 password posture + PII trace metadata (aggregates only).",
        "- **Restriction:** No credentials, hashes, or per-subject PII in this file.",
        "",
        "## Aggregated database metrics",
        "",
    ]
    if "error" in stats:
        lines.append(f"- **error:** {stats['error']}")
    else:
        for k in sorted(stats):
            lines.append(f"- `{k}`: {stats[k]}")
    lines.extend(
        [
            "",
            "## Connectivity (deep-health style)",
            "",
        ]
    )
    for name, payload in sorted(health.items()):
        lines.append(f"### {name}")
        for pk, pv in payload.items():
            lines.append(f"- {pk}: {pv}")
        lines.append("")
    lines.extend(
        [
            "## S3 backup compliance (AWS API probe)",
            "",
        ]
    )
    for k in sorted(s3):
        lines.append(f"- {k}: {s3[k]}")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Object-level SSE for uploads is enforced in GitHub Actions (`backup_daily.yml`).",
            "- Bucket default encryption, PAB y región: sonda de este script + `scripts/validate_backup_s3_bucket.sh` en CI.",
            "- Guía de ejecución: `backend/scripts/README.md`.",
            "",
        ]
    )
    return "\n".join(lines)


async def main_async(*, out_path: Path) -> int:
    stats, health, s3 = await asyncio.gather(
        _stats_block(),
        _gather_health(),
        asyncio.to_thread(_s3_backup_compliance_probe),
    )
    body = _render_md(stats=stats, health=health, s3=s3)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    print(f"[generate_compliance_report] wrote {out_path}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Informe compliance sanitizado (M&A).")
    p.add_argument(
        "--out",
        type=Path,
        default=REPORTS_DIR / "compliance_evidence_LATAM_Q2.md",
        help="Ruta del markdown de salida.",
    )
    args = p.parse_args()
    return asyncio.run(main_async(out_path=args.out.resolve()))


if __name__ == "__main__":
    raise SystemExit(main())
