#!/usr/bin/env python3
"""
Marcado por lotes hito 1.4 (needs_rehash + pseudonymized_at en clientes).

Usa RPCs SECURITY DEFINER expuestas solo a service_role (ver migracion
``20260427120000_compliance_hito_14_columns_and_stats.sql``).

No imprime emails, hashes ni DATABASE_URL.

  python backend/scripts/compliance_mark.py --dry-run
  python backend/scripts/compliance_mark.py --apply --batch-size 500 --max-rounds 100
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
for env_path in (ROOT / ".env", REPO / ".env"):
    if env_path.exists():
        load_dotenv(env_path)


def _rpc_rows_affected(raw: object) -> int:
    if raw is None:
        return 0
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, list) and raw:
        try:
            return int(raw[0])
        except (TypeError, ValueError):
            return 0
    try:
        return int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


async def _stats(client: object) -> dict[str, object]:
    try:
        res = client.rpc("compliance_hito_14_stats", {}).execute()
    except Exception as exc:
        return {"error": f"{type(exc).__name__}"}
    data = getattr(res, "data", None)
    if isinstance(data, dict):
        return data
    return {}


async def _run_round(client: object, *, batch: int, fn: str) -> int:
    try:
        res = client.rpc(fn, {"p_limit": batch}).execute()
    except Exception as exc:
        print(f"[compliance_mark] ERROR RPC {fn}: {type(exc).__name__}", file=sys.stderr)
        raise RuntimeError(f"rpc_failed:{fn}") from exc
    return _rpc_rows_affected(getattr(res, "data", None))


async def main_async(*, apply: bool, batch: int, max_rounds: int) -> int:
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    if not url or not key:
        print("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY / SUPABASE_SERVICE_KEY", file=sys.stderr)
        return 2

    from supabase import create_client

    client = create_client(url, key)

    before = await _stats(client)
    print("[compliance_mark] stats_before:", {k: before.get(k) for k in sorted(before)})

    if not apply:
        print("[compliance_mark] dry-run: no se invocan RPCs de escritura.")
        return 0

    total_u = total_c = 0
    for rnd in range(max_rounds):
        u = await _run_round(client, batch=batch, fn="compliance_batch_mark_usuarios_needs_rehash")
        c = await _run_round(client, batch=batch, fn="compliance_batch_stamp_clientes_pseudonymized")
        total_u += u
        total_c += c
        print(f"[compliance_mark] round={rnd + 1} usuarios_rows={u} clientes_rows={c}")
        if u == 0 and c == 0:
            break

    after = await _stats(client)
    print("[compliance_mark] stats_after:", {k: after.get(k) for k in sorted(after)})
    print(f"[compliance_mark] totals usuarios_updates={total_u} clientes_updates={total_c}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Marcado compliance 1.4 por lotes (Supabase service_role).")
    p.add_argument("--dry-run", action="store_true", help="Solo estadísticas agregadas, sin escrituras.")
    p.add_argument("--apply", action="store_true", help="Ejecutar RPCs de batch.")
    p.add_argument("--batch-size", type=int, default=500, help="p_limit por RPC (1–5000 clamp en SQL).")
    p.add_argument("--max-rounds", type=int, default=200, help="Máximo de rondas por familia de RPC.")
    args = p.parse_args()

    if args.apply and args.dry_run:
        print("Elige solo uno de --apply o --dry-run", file=sys.stderr)
        return 2
    if not args.apply and not args.dry_run:
        print("Indica --dry-run o --apply", file=sys.stderr)
        return 2

    return asyncio.run(
        main_async(apply=args.apply, batch=max(1, args.batch_size), max_rounds=max(1, args.max_rounds))
    )


if __name__ == "__main__":
    raise SystemExit(main())
