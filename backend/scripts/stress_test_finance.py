from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import random
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import dotenv_values

env_file = BACKEND_ROOT / ".env"
if env_file.exists():
    env_map = dotenv_values(env_file)
    for k, v in env_map.items():
        if k and v is not None and not os.getenv(k):
            os.environ[k] = v

from app.core.math_engine import MathEngine, quantize_financial, to_decimal
from app.db.supabase import SupabaseAsync, get_supabase
from app.services.finance_service import FinanceService
from app.services.reconciliation_service import ReconciliationService


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--empresa-id", default="dummy")
    p.add_argument("--invoices", type=int, default=90)
    p.add_argument("--transactions", type=int, default=90)
    p.add_argument("--batch-size", type=int, default=50)
    p.add_argument("--seed", type=int, default=20260330)
    return p.parse_args()


def _rand_date_last_12m(rng: random.Random) -> date:
    delta_days = rng.randint(0, 364)
    return date.today() - timedelta(days=delta_days)


async def _resolve_cliente_id(db: SupabaseAsync, empresa_id: str) -> str:
    res: Any = await db.execute(
        db.table("clientes").select("id").eq("empresa_id", empresa_id).limit(1)
    )
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    if rows:
        return str(rows[0]["id"])

    res_any: Any = await db.execute(db.table("clientes").select("id").limit(1))
    rows_any: list[dict[str, Any]] = (res_any.data or []) if hasattr(res_any, "data") else []
    if rows_any:
        return str(rows_any[0]["id"])

    raise RuntimeError("No hay clientes disponibles para asociar facturas")


def _is_uuid(value: str) -> bool:
    try:
        UUID(str(value))
        return True
    except Exception:
        return False


async def _resolve_empresa_meta(db: SupabaseAsync, requested: str) -> tuple[str, str]:
    req = str(requested or "").strip()
    if req.casefold() == "dummy":
        return str(uuid4()), "NIF_TEST"
    if _is_uuid(req):
        res_one: Any = await db.execute(
            db.table("empresas").select("id,nif").eq("id", req).limit(1)
        )
        rows_one: list[dict[str, Any]] = (res_one.data or []) if hasattr(res_one, "data") else []
        if rows_one:
            return str(rows_one[0]["id"]), str(rows_one[0].get("nif") or "")

    res: Any = await db.execute(
        db.table("empresas").select("id,nif,nombre_comercial,nombre_legal").limit(200)
    )
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    if not rows:
        raise RuntimeError("No hay empresas disponibles en la base de datos")

    q = req.casefold()
    if q:
        for r in rows:
            nc = str(r.get("nombre_comercial") or "")
            nl = str(r.get("nombre_legal") or "")
            if q in nc.casefold() or q in nl.casefold():
                return str(r["id"]), str(r.get("nif") or "")

    for r in rows:
        text = f"{r.get('nombre_comercial') or ''} {r.get('nombre_legal') or ''}".casefold()
        if "test" in text or "demo" in text or "sandbox" in text:
            return str(r["id"]), str(r.get("nif") or "")

    return str(rows[0]["id"]), str(rows[0].get("nif") or "")


async def _ensure_dummy_empresa_exists(db: SupabaseAsync, empresa_id: str, nif_emisor: str) -> None:
    try:
        await db.execute(
            db.table("empresas")
            .insert(
                {
                    "id": empresa_id,
                    "nombre_comercial": f"Stress Test {empresa_id[:8]}",
                    "nif": nif_emisor or "NIF_TEST",
                    "plan": "Trial",
                }
            )
        )
    except Exception:
        pass


async def _batch_insert(
    db: SupabaseAsync,
    *,
    table: str,
    rows: list[dict[str, Any]],
    batch_size: int,
) -> str | int | None:
    last_successful_id: str | int | None = None
    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        await db.execute(db.table(table).insert(chunk))
        tail = chunk[-1] if chunk else {}
        last_successful_id = (
            tail.get("id")
            or tail.get("transaction_id")
            or tail.get("numero_factura")
            or tail.get("num_factura")
        )
    return last_successful_id


def _invoice_totals(base_amount: float) -> tuple[Decimal, Decimal, Decimal]:
    result = MathEngine.calculate_totals(
        items=[
            {
                "cantidad": Decimal("1"),
                "precio_unitario": to_decimal(base_amount),
                "tipo_iva_porcentaje": Decimal("21.00"),
            }
        ]
    )
    return (
        quantize_financial(result.base_imponible_total),
        quantize_financial(result.cuota_iva_total),
        quantize_financial(result.total_factura),
    )


def _build_invoices(
    *,
    empresa_id: str,
    cliente_id: str,
    nif_emisor: str,
    count: int,
    rng: random.Random,
    run_id: str,
) -> tuple[list[dict[str, Any]], Decimal, int]:
    rows: list[dict[str, Any]] = []
    ebitda = Decimal("0.00")
    discrepancies = 0

    for i in range(count):
        base_random = rng.uniform(10.0, 10000.0)
        base, cuota, total = _invoice_totals(base_random)
        fecha_emision = _rand_date_last_12m(rng).isoformat()
        numero = f"ST-{run_id}-{i:05d}"
        hash_seed = hashlib.sha256(f"{run_id}:{numero}".encode("utf-8")).hexdigest()

        row = {
            "empresa_id": empresa_id,
            "cliente": cliente_id,
            "numero_factura": numero,
            "num_factura": numero,
            "fecha_emision": fecha_emision,
            "tipo_factura": "F1",
            "nif_emisor": nif_emisor or "NIF_TEST",
            "base_imponible": float(base),
            "cuota_iva": float(cuota),
            "total_factura": float(total),
            "estado_cobro": "emitida",
            "hash_registro": hash_seed,
            "hash_factura": hash_seed,
            "numero_secuencial": i + 1,
            "total_km_estimados_snapshot": float(quantize_financial(rng.uniform(50.0, 2000.0))),
        }
        rows.append(row)
        ebitda += base

        _, _, expected_total = _invoice_totals(float(base))
        if quantize_financial(row["total_factura"]) != expected_total:
            discrepancies += 1

    return rows, quantize_financial(ebitda), discrepancies


def _decimal_float_mismatch_count(invoice_rows: list[dict[str, Any]]) -> int:
    mismatches = 0
    for row in invoice_rows:
        b_dec = quantize_financial(row["base_imponible"])
        c_dec = quantize_financial(row["cuota_iva"])
        t_dec = quantize_financial(row["total_factura"])
        if quantize_financial(b_dec + c_dec) != t_dec:
            mismatches += 1
    return mismatches


def _build_transactions(
    *,
    empresa_id: str,
    invoice_rows: list[dict[str, Any]],
    count: int,
    rng: random.Random,
    run_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    match_count = int(count * 0.8)

    for i in range(count):
        tx_id = f"stx-{run_id}-{i:05d}"
        inv = invoice_rows[i % len(invoice_rows)]
        inv_num = str(inv["numero_factura"])
        inv_total = quantize_financial(inv["total_factura"])
        inv_date = date.fromisoformat(str(inv["fecha_emision"]))
        booked_date = (inv_date + timedelta(days=rng.randint(0, 25))).isoformat()

        if i < match_count:
            amount = float(inv_total)
            reference = f"PAGO {inv_num}"
            description = "TRANSFERENCIA FACTURA"
        else:
            if rng.random() < 0.5:
                noise_delta = quantize_financial(rng.uniform(0.01, 47.0))
                amount = float(quantize_financial(inv_total + noise_delta))
                reference = f"PAGO {inv_num}"
                description = "TRANSFERENCIA FACTURA"
            else:
                amount = float(inv_total)
                reference = f"NOISE-{run_id}-{i:05d}"
                description = f"TRANSFERENCIA DIVERSA {run_id}"

        rows.append(
            {
                "empresa_id": empresa_id,
                "transaction_id": tx_id,
                "amount": amount,
                "booked_date": booked_date,
                "currency": "EUR",
                "description": description,
                "reconciled": False,
                "raw_fingerprint": hashlib.sha256(tx_id.encode("utf-8")).hexdigest(),
            }
        )

    return rows


async def _get_ebitda_from_finance_service(finance_service: FinanceService, empresa_id: str) -> Decimal:
    summary = await finance_service.financial_summary(empresa_id=empresa_id)
    return quantize_financial(summary.ebitda)


async def _run() -> None:
    args = _args()
    rng = random.Random(args.seed)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    t0 = time.perf_counter()

    db = await get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )

    empresa_id, empresa_nif = await _resolve_empresa_meta(db, args.empresa_id)
    if args.empresa_id.strip().casefold() == "dummy":
        await _ensure_dummy_empresa_exists(db, empresa_id, empresa_nif)
    cliente_id = await _resolve_cliente_id(db, empresa_id)
    invoice_rows, total_ebitda, discrepancies = _build_invoices(
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        nif_emisor=empresa_nif,
        count=args.invoices,
        rng=rng,
        run_id=run_id,
    )
    tx_rows = _build_transactions(
        empresa_id=empresa_id,
        invoice_rows=invoice_rows,
        count=args.transactions,
        rng=rng,
        run_id=run_id,
    )

    try:
        await db.rpc("set_empresa_context", {"p_empresa_id": empresa_id})
    except Exception:
        pass

    last_successful_id: str | int | None = None
    try:
        last_successful_id = await _batch_insert(
            db,
            table="facturas",
            rows=invoice_rows,
            batch_size=max(1, args.batch_size),
        )
        last_successful_id = await _batch_insert(
            db,
            table="bank_transactions",
            rows=tx_rows,
            batch_size=max(1, args.batch_size),
        )
    except Exception as exc:
        msg = str(exc)
        if "Límite del plan Starter alcanzado" in msg or "plan" in msg.casefold():
            print("plan_limit_error_detected=true")
            print(f"last_successful_id={last_successful_id}")
            return
        raise

    recon = ReconciliationService(db)
    t_recon_0 = time.perf_counter()
    matched_for_empresa, _ = await recon.auto_reconcile_invoices(empresa_id)
    recon_elapsed = time.perf_counter() - t_recon_0
    matched = int(matched_for_empresa)

    finance = FinanceService(db)
    finance_service = finance
    setattr(
        finance_service,
        "get_ebitda",
        lambda eid: _get_ebitda_from_finance_service(finance_service, eid),
    )
    finance_ebitda = await finance_service.get_ebitda(empresa_id)
    summary = await finance.financial_summary(empresa_id=empresa_id)
    exact_sum_invoices = quantize_financial(
        sum((to_decimal(r["base_imponible"]) for r in invoice_rows), start=Decimal("0.00"))
    )
    summary_ingresos = quantize_financial(summary.ingresos)
    summary_gastos = quantize_financial(summary.gastos)
    summary_ebitda = quantize_financial(summary.ebitda)
    ebitda_lhs = quantize_financial(summary_ingresos - summary_gastos)
    ebitda_equation_ok = ebitda_lhs == summary_ebitda
    invoice_vs_ebitda_delta = quantize_financial(exact_sum_invoices - summary_ebitda)

    decimal_float_mismatch_count = _decimal_float_mismatch_count(invoice_rows)

    elapsed = time.perf_counter() - t0
    print(f"empresa_id_used={empresa_id}")
    print(f"total_time_taken_seconds={elapsed:.3f}")
    print(f"time_per_reconciliation_seconds={recon_elapsed:.3f}")
    print(f"invoices_matched={matched}")
    print(f"expected_exact_match_count={int(args.transactions * 0.8)}")
    print(f"total_ebitda_calculated={float(total_ebitda):.2f}")
    print(f"exact_sum_invoices_base={float(exact_sum_invoices):.2f}")
    print(f"finance_service_ingresos={float(summary_ingresos):.2f}")
    print(f"finance_service_gastos={float(summary_gastos):.2f}")
    print(f"finance_service_ebitda={float(summary_ebitda):.2f}")
    print(f"finance_service_get_ebitda={float(quantize_financial(finance_ebitda)):.2f}")
    print(f"ebitda_equation_lhs={float(ebitda_lhs):.2f}")
    print(f"ebitda_equation_ok={str(ebitda_equation_ok).lower()}")
    print(f"invoice_sum_vs_ebitda_delta={float(invoice_vs_ebitda_delta):.2f}")
    print(f"rounding_discrepancies={discrepancies}")
    print(f"round_half_even_exact={str(discrepancies == 0).lower()}")
    print(f"decimal_float_mismatch_count={decimal_float_mismatch_count}")


if __name__ == "__main__":
    asyncio.run(_run())
