from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

ENV_FILE = BACKEND_ROOT / ".env"
if ENV_FILE.exists():
    env_map = dotenv_values(ENV_FILE)
    for k, v in env_map.items():
        if k and v is not None and not os.getenv(k):
            os.environ[k] = v

from app.core.math_engine import quantize_financial
from app.db.supabase import get_supabase
from app.services.alert_service import send_critical_alert


def _endpoint(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip()


async def _http_ok(url: str) -> tuple[bool, int]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
        return r.status_code == 200, r.status_code
    except Exception:
        return False, 0


def _math_check() -> tuple[bool, str]:
    # ROUND_HALF_EVEN: 1.005 -> 1.00 ; 1.015 -> 1.02
    a = quantize_financial("1.005")
    b = quantize_financial("1.015")
    ok = str(a) == "1.00" and str(b) == "1.02"
    return ok, f"math_round_half_even:1.005={a};1.015={b}"


async def _last_audit_logs_tail(limit: int = 5) -> list[str]:
    try:
        db = await get_supabase(
            jwt_token=None,
            allow_service_role_bypass=True,
            log_service_bypass_warning=False,
        )
        res: Any = await db.execute(
            db.table("audit_logs")
            .select("created_at,table_name,action,record_id")
            .order("created_at", desc=True)
            .limit(limit)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            return ["<audit_logs vacío>"]
        out: list[str] = []
        for row in rows:
            out.append(
                f"{row.get('created_at')} | {row.get('table_name')} | "
                f"{row.get('action')} | record_id={row.get('record_id')}"
            )
        return out
    except Exception as exc:
        return [f"<audit_logs_error: {exc}>"]


async def main() -> int:
    backend_ready_url = _endpoint("SENTINEL_BACKEND_READY_URL", "http://localhost:8000/ready")
    frontend_url = _endpoint("SENTINEL_FRONTEND_URL", "http://localhost:3000/")
    verifactu_url = _endpoint(
        "SENTINEL_VERIFACTU_URL",
        "http://localhost:8000/api/v1/health/verifactu",
    )

    checks: list[tuple[str, bool, str]] = []

    ok_be, st_be = await _http_ok(backend_ready_url)
    checks.append(("backend_ready", ok_be, f"url={backend_ready_url} status={st_be}"))

    ok_fe, st_fe = await _http_ok(frontend_url)
    checks.append(("frontend_root", ok_fe, f"url={frontend_url} status={st_fe}"))

    ok_vf, st_vf = await _http_ok(verifactu_url)
    checks.append(("verifactu_health", ok_vf, f"url={verifactu_url} status={st_vf}"))

    ok_math, msg_math = _math_check()
    checks.append(("math_check", ok_math, msg_math))

    failed = [c for c in checks if not c[1]]
    if not failed:
        print("sentinel_status=ok")
        for name, _, details in checks:
            print(f"{name}=ok {details}")
        return 0

    tail = await _last_audit_logs_tail(limit=5)
    ts = datetime.now(timezone.utc).isoformat()
    body_lines = [
        f"timestamp={ts}",
        "sentinel_status=failed",
        "",
        "failed_checks:",
    ]
    for name, _, details in failed:
        body_lines.append(f"- {name}: {details}")
    body_lines.extend(["", "audit_logs_tail_last_5:"])
    body_lines.extend([f"- {line}" for line in tail])
    body = "\n".join(body_lines)

    subject = f"[CRITICAL] Sentinel Watchdog Failure ({len(failed)} checks)"
    try:
        send_critical_alert(subject=subject, body=body)
        print("alert_email=sent")
    except Exception as exc:
        print(f"alert_email=failed error={exc}")

    for name, ok, details in checks:
        print(f"{name}={'ok' if ok else 'failed'} {details}")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
