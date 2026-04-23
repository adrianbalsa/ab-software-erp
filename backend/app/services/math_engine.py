from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.math_engine import MathEngine
from app.db.supabase import SupabaseAsync
from app.services.audit_logs_service import AuditLogsService


class BankingMathEngineService:
    """Reglas de conciliación bancaria (importe exacto + ventana de fecha)."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def match_transactions_to_invoices(
        self,
        *,
        empresa_id: str,
        pending_transactions: list[dict[str, Any]],
        pending_invoices: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        matches = MathEngine.match_transactions_to_invoices(
            transactions=pending_transactions,
            pending_invoices=pending_invoices,
            date_tolerance_days=3,
        )
        if not matches:
            return []

        out: list[dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()
        for m in matches:
            factura_id = int(m["factura_id"])
            tx_id = str(m["transaction_id"])
            res_tx: Any = await self._db.execute(
                self._db.table("bank_transactions")
                .select("booked_date,amount")
                .eq("empresa_id", empresa_id)
                .eq("transaction_id", tx_id)
                .limit(1)
            )
            tx_rows = (res_tx.data or []) if hasattr(res_tx, "data") else []
            booked_date = str((tx_rows[0] if tx_rows else {}).get("booked_date") or "")[:10]

            await self._db.execute(
                self._db.table("facturas")
                .update(
                    {
                        "estado_cobro": "PAID",
                        "payment_status": "PAID",
                        "pago_id": tx_id,
                        "matched_transaction_id": tx_id,
                        "fecha_cobro_real": booked_date or datetime.now(timezone.utc).date().isoformat(),
                    }
                )
                .eq("empresa_id", empresa_id)
                .eq("id", factura_id)
            )
            await self._db.execute(
                self._db.table("bank_transactions")
                .update(
                    {
                        "reconciled": True,
                        "status_reconciled": "reconciled",
                        "internal_status": "reconciled",
                        "updated_at": now_iso,
                    }
                )
                .eq("empresa_id", empresa_id)
                .eq("transaction_id", tx_id)
            )
            await AuditLogsService(self._db).log_bank_reconciliation(
                empresa_id=empresa_id,
                transaction_id=tx_id,
                factura_id=factura_id,
                user_id=None,
            )
            out.append({"factura_id": factura_id, "transaction_id": tx_id, "status": "PAID"})
        return out
