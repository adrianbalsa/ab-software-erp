"""
Agregación de saldo pendiente por cliente (misma lógica que el dashboard financiero).

Usada por ``finance_dashboard`` y por validaciones de crédito (p. ej. alta de portes).
"""

from __future__ import annotations

from typing import Any

from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync


def _month_key(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if len(s) >= 7 and s[4] == "-":
        return s[:7]
    return None


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


async def aggregate_pending_and_trend(
    db: SupabaseAsync,
    empresa_id: str,
    *,
    months_for_trend: list[str] | None,
) -> tuple[dict[str, float], dict[str, dict[str, float]], bool]:
    """
    Facturas no cobradas por cliente (o portes no facturados si no hay facturas).
    Si ``months_for_trend`` se informa, rellena cobrado/pendiente por mes (misma consulta).
    """
    months = months_for_trend or []
    trend_raw: dict[str, dict[str, float]] = {m: {"cobrado": 0.0, "pendiente": 0.0} for m in months}

    res_facturas: Any = await db.execute(
        db.table("facturas")
        .select("cliente, total_factura, estado_cobro, fecha_emision")
        .eq("empresa_id", empresa_id)
    )
    facturas_rows: list[dict[str, Any]] = (res_facturas.data or []) if hasattr(res_facturas, "data") else []
    use_portes_fallback = len(facturas_rows) == 0
    pending_by_client: dict[str, float] = {}

    if not use_portes_fallback:
        for row in facturas_rows:
            client_id = str(row.get("cliente") or "").strip()
            amount = max(0.0, _to_float(row.get("total_factura")))
            status = str(row.get("estado_cobro") or "").strip().lower()
            is_paid = status == "cobrada"

            mk = _month_key(row.get("fecha_emision"))
            if mk in trend_raw:
                if is_paid:
                    trend_raw[mk]["cobrado"] += amount
                else:
                    trend_raw[mk]["pendiente"] += amount

            if not is_paid and client_id:
                pending_by_client[client_id] = pending_by_client.get(client_id, 0.0) + amount
    else:
        res_portes: Any = await db.execute(
            filter_not_deleted(
                db.table("portes")
                .select("cliente_id, precio_pactado, fecha, estado")
                .eq("empresa_id", empresa_id)
            )
        )
        portes_rows: list[dict[str, Any]] = (res_portes.data or []) if hasattr(res_portes, "data") else []
        for row in portes_rows:
            client_id = str(row.get("cliente_id") or "").strip()
            amount = max(0.0, _to_float(row.get("precio_pactado")))
            estado = str(row.get("estado") or "").strip().lower()
            is_pending = estado != "facturado"

            mk = _month_key(row.get("fecha"))
            if mk in trend_raw:
                if is_pending:
                    trend_raw[mk]["pendiente"] += amount
                else:
                    trend_raw[mk]["cobrado"] += amount

            if is_pending and client_id:
                pending_by_client[client_id] = pending_by_client.get(client_id, 0.0) + amount

    return pending_by_client, trend_raw, use_portes_fallback
