"""Marca cuentas con password SHA-256 legacy para reset obligatorio.

Uso:
  python scripts/mark_legacy_sha256_passwords.py --limit 1000

Requiere credenciales Supabase de service role en el entorno.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")

from app.db.supabase import get_supabase  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402


async def _run(limit: int) -> int:
    db = await get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )
    return await AuthService(db).mark_legacy_sha256_passwords_for_reset(limit=limit)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Activa password_must_reset en usuarios con password_hash SHA-256 legacy.",
    )
    parser.add_argument("--limit", type=int, default=1000, help="Máximo de usuarios a inspeccionar")
    args = parser.parse_args()
    marked = asyncio.run(_run(args.limit))
    print(f"password_must_reset activado en {marked} cuenta(s).")


if __name__ == "__main__":
    main()
