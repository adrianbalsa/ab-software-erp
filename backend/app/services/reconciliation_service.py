from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.db.supabase import SupabaseAsync

_log = logging.getLogger(__name__)


def _invoice_number(row: dict[str, Any]) -> str:
    return str(row.get("numero_factura") or row.get("num_factura") or "").strip()


def _two_dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def match_unreconciled_to_invoices(
    *,
    bank_rows: list[dict[str, Any]],
    facturas_emitidas: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Reglas:
    - Importe de movimiento **estrictamente positivo** y, en dos decimales, **igual** a ``total_factura``.
    - ``numero_factura`` (o ``num_factura``) debe aparecer en ``description`` (comparación case-insensitive).
    - Cada factura y cada movimiento se emparejan como máximo una vez (orden estable por ``id`` / ``transaction_id``).
    """
    invs = sorted(
        (
            f
            for f in facturas_emitidas
            if _two_dec(f.get("total_factura")) > 0 and _invoice_number(f)
        ),
        key=lambda x: int(x.get("id") or 0),
    )
    txs = sorted(
        (t for t in bank_rows if _two_dec(t.get("amount")) > 0),
        key=lambda t: str(t.get("transaction_id") or ""),
    )

    matched_inv: set[int] = set()
    matched_tx: set[str] = set()
    result: list[dict[str, Any]] = []

    for tx in txs:
        tx_id = str(tx.get("transaction_id") or "").strip()
        if not tx_id or tx_id in matched_tx:
            continue
        amt = _two_dec(tx.get("amount"))
        desc = str(tx.get("description") or "")
        desc_fold = desc.casefold()

        for inv in invs:
            fid = int(inv.get("id") or 0)
            if fid in matched_inv:
                continue
            total = _two_dec(inv.get("total_factura"))
            if total != amt:
                continue
            num = _invoice_number(inv)
            if not num:
                continue
            if num.casefold() not in desc_fold:
                continue

            matched_inv.add(fid)
            matched_tx.add(tx_id)
            bd = tx.get("booked_date")
            if hasattr(bd, "isoformat"):
                fecha_cobro = bd.isoformat()[:10]
            else:
                fecha_cobro = str(bd)[:10] if bd else date.today().isoformat()
            result.append(
                {
                    "factura_id": fid,
                    "transaction_id": tx_id,
                    "total_factura": float(total),
                    "importe_movimiento": float(amt),
                    "fecha_cobro_real": fecha_cobro,
                }
            )
            break

    return result


class ReconciliationService:
    """Conciliación automática facturas ↔ bank_transactions."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def auto_reconcile_invoices(self, empresa_id: str) -> tuple[int, list[dict[str, Any]]]:
        """
        Cruza movimientos no conciliados (importe > 0) con facturas ``estado_cobro='emitida'``.
        Actualiza factura (cobrada, fecha_cobro_real, matched_transaction_id, pago_id) y marca el movimiento.
        """
        res_tx: Any = await self._db.execute(
            self._db.table("bank_transactions")
            .select("transaction_id, amount, description, booked_date, reconciled")
            .eq("empresa_id", empresa_id)
            .eq("reconciled", False)
        )
        tx_rows: list[dict[str, Any]] = (res_tx.data or []) if hasattr(res_tx, "data") else []

        res_f: Any = await self._db.execute(
            self._db.table("facturas")
            .select("id, total_factura, numero_factura, num_factura, estado_cobro")
            .eq("empresa_id", empresa_id)
            .eq("estado_cobro", "emitida")
        )
        fac_rows: list[dict[str, Any]] = (res_f.data or []) if hasattr(res_f, "data") else []

        pairs = match_unreconciled_to_invoices(bank_rows=tx_rows, facturas_emitidas=fac_rows)
        detalle: list[dict[str, Any]] = []

        for p in pairs:
            fid = int(p["factura_id"])
            tx_id = str(p["transaction_id"])
            fecha = str(p["fecha_cobro_real"])[:10]

            await self._db.execute(
                self._db.table("facturas")
                .update(
                    {
                        "estado_cobro": "cobrada",
                        "pago_id": tx_id,
                        "matched_transaction_id": tx_id,
                        "fecha_cobro_real": fecha,
                    }
                )
                .eq("id", fid)
                .eq("empresa_id", empresa_id)
                .eq("estado_cobro", "emitida")
            )

            now_iso = datetime.now(timezone.utc).isoformat()
            await self._db.execute(
                self._db.table("bank_transactions")
                .update({"reconciled": True, "updated_at": now_iso})
                .eq("empresa_id", empresa_id)
                .eq("transaction_id", tx_id)
            )

            detalle.append(
                {
                    "factura_id": fid,
                    "transaction_id": tx_id,
                    "total_factura": p["total_factura"],
                    "importe_movimiento": p["importe_movimiento"],
                    "fecha_cobro_real": fecha,
                }
            )

        if pairs:
            _log.info(
                "conciliación automática: empresa_id=%s coincidencias=%s",
                empresa_id,
                len(pairs),
            )

        return len(pairs), detalle
