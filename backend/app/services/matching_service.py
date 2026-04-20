"""
Motor de conciliación bancaria probabilística (importe exacto + fuzzy referencia + ventana de fechas).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from app.db.supabase import SupabaseAsync
from app.schemas.banking import ConciliationCandidate, FacturaConciliacion, Transaccion
from app.services import match_fuzzy as mf
from app.services.audit_logs_service import AuditLogsService

_log = logging.getLogger(__name__)


class MatchingService:
    """Emparejamiento movimientos bancarios ↔ facturas pendientes de cobro/pago."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def load_unreconciled_transactions(self, *, empresa_id: str) -> list[Transaccion]:
        res: Any = await self._db.execute(
            self._db.table("bank_transactions")
            .select("*")
            .eq("empresa_id", empresa_id)
            .eq("reconciled", False)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[Transaccion] = []
        for r in rows:
            if mf.two_dec(r.get("amount")) == 0:
                continue
            tid = str(r.get("transaction_id") or "").strip()
            if not tid:
                continue
            out.append(Transaccion.from_bank_row(dict(r)))
        return out

    async def get_unreconciled_transaction(
        self,
        *,
        empresa_id: str,
        transaction_id: str,
    ) -> Transaccion | None:
        """Un movimiento de ``bank_transactions`` no conciliado y con importe distinto de cero."""
        tid = str(transaction_id or "").strip()
        if not tid:
            return None
        res_tx: Any = await self._db.execute(
            self._db.table("bank_transactions")
            .select("*")
            .eq("empresa_id", empresa_id)
            .eq("transaction_id", tid)
            .limit(1)
        )
        tx_rows: list[dict[str, Any]] = (res_tx.data or []) if hasattr(res_tx, "data") else []
        if not tx_rows:
            return None
        row = dict(tx_rows[0])
        if row.get("reconciled") is True:
            return None
        tx = Transaccion.from_bank_row(row)
        if mf.two_dec(tx.amount) == 0:
            return None
        return tx

    async def load_pending_invoices(self, *, empresa_id: str) -> list[FacturaConciliacion]:
        """
        Facturas emitidas/recibidas pendientes de liquidación: no cobradas ni pagadas, total > 0.
        """
        res: Any = await self._db.execute(
            self._db.table("facturas")
            .select(
                "id, total_factura, numero_factura, num_factura, fecha_emision, estado_cobro, "
                "empresa_id, cliente, tipo_factura"
            )
            .eq("empresa_id", empresa_id)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out_raw: list[dict[str, Any]] = []
        for r in rows:
            st = str(r.get("estado_cobro") or "").strip().lower()
            if st in ("cobrada", "pagada"):
                continue
            if mf.two_dec(r.get("total_factura")) <= 0:
                continue
            out_raw.append(dict(r))
        enriched = await self._enriquecer_nombres_cliente(empresa_id=empresa_id, facturas=out_raw)
        return [FacturaConciliacion.from_factura_row(r) for r in enriched]

    async def _enriquecer_nombres_cliente(
        self, *, empresa_id: str, facturas: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        ids: set[str] = set()
        for r in facturas:
            cid = r.get("cliente")
            if cid is not None:
                ids.add(str(cid).strip())
        if not ids:
            return [{**r, "cliente_nombre": None} for r in facturas]
        nombres: dict[str, str] = {}
        try:
            res: Any = await self._db.execute(
                self._db.table("clientes")
                .select("id, nombre, nombre_comercial")
                .eq("empresa_id", empresa_id)
                .in_("id", list(ids))
            )
            for row in (res.data or []) if hasattr(res, "data") else []:
                i = str(row.get("id") or "").strip()
                if not i:
                    continue
                nc = (row.get("nombre_comercial") or row.get("nombre") or "").strip()
                nombres[i] = nc or i
        except Exception:
            pass
        enriched: list[dict[str, Any]] = []
        for r in facturas:
            cid = str(r.get("cliente") or "").strip()
            enriched.append({**r, "cliente_nombre": nombres.get(cid)})
        return enriched

    def find_best_candidates(
        self,
        *,
        transactions: list[Transaccion],
        invoices: list[FacturaConciliacion],
        threshold: float = 0.85,
    ) -> tuple[list[ConciliationCandidate], set[int], set[str]]:
        """
        Para cada movimiento, elige la factura con mayor S_c entre las de importe exacto;
        solo se acepta si S_c >= ``threshold``. Emparejamiento 1:1 (cada factura a lo sumo un movimiento).
        """
        inv_sorted = sorted(invoices, key=lambda x: x.id)
        tx_sorted = sorted(transactions, key=lambda t: t.transaction_id)
        used_inv: set[int] = set()
        used_tx: set[str] = set()
        results: list[ConciliationCandidate] = []

        for tx in tx_sorted:
            tx_id = tx.transaction_id.strip()
            if not tx_id or tx_id in used_tx:
                continue
            best_score = -1.0
            best_inv: FacturaConciliacion | None = None
            for inv in inv_sorted:
                fid = inv.id
                if fid in used_inv:
                    continue
                if not mf.amount_matches_invoice(tx, inv):
                    continue
                s_c = mf.combined_confidence_score(transaction=tx, invoice=inv)
                if s_c > best_score:
                    best_score = s_c
                    best_inv = inv
            if best_inv is None or best_score < threshold:
                continue
            ref_s = mf.reference_score(tx, best_inv)
            txd = mf.parse_iso_date(tx.booked_date)
            invd = mf.parse_iso_date(best_inv.fecha_emision)
            dscore = mf.date_alignment_score(txd, invd)
            booked_s = tx.booked_date_iso()
            inv_s = best_inv.fecha_emision_iso()
            best = ConciliationCandidate(
                transaction_id=tx_id,
                factura_id=best_inv.id,
                score=round(best_score, 4),
                reference_score=round(ref_s, 4),
                date_score=round(dscore, 4),
                amount=float(mf.two_dec(tx.amount)),
                invoice_number=best_inv.invoice_number() or None,
                booked_date=booked_s,
                invoice_date=inv_s,
            )
            results.append(best)
            used_inv.add(best.factura_id)
            used_tx.add(best.transaction_id)

        return results, used_inv, used_tx

    async def get_candidates(
        self,
        *,
        empresa_id: str,
        transaction_id: str,
    ) -> list[ConciliationCandidate]:
        """
        Candidatos fuzzy para **un** movimiento: todas las facturas con importe exacto,
        ordenadas por S_c descendente (sin restricción 1:1 global; eso aplica en ``find_best_candidates``).
        """
        tid = str(transaction_id or "").strip()
        tx = await self.get_unreconciled_transaction(empresa_id=empresa_id, transaction_id=tid)
        if tx is None:
            return []

        invs = await self.load_pending_invoices(empresa_id=empresa_id)
        candidates: list[ConciliationCandidate] = []
        for inv in invs:
            if not mf.amount_matches_invoice(tx, inv):
                continue
            best_score = mf.combined_confidence_score(transaction=tx, invoice=inv)
            ref_s = mf.reference_score(tx, inv)
            txd = mf.parse_iso_date(tx.booked_date)
            invd = mf.parse_iso_date(inv.fecha_emision)
            dscore = mf.date_alignment_score(txd, invd)
            booked_s = tx.booked_date_iso()
            inv_s = inv.fecha_emision_iso()
            candidates.append(
                ConciliationCandidate(
                    transaction_id=tid,
                    factura_id=inv.id,
                    score=round(float(best_score), 4),
                    reference_score=round(ref_s, 4),
                    date_score=round(dscore, 4),
                    amount=float(mf.two_dec(tx.amount)),
                    invoice_number=inv.invoice_number() or None,
                    booked_date=booked_s,
                    invoice_date=inv_s,
                )
            )
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    async def find_matches(
        self,
        *,
        empresa_id: str,
        threshold: float = 0.85,
    ) -> dict[str, Any]:
        """Carga datos y devuelve emparejamientos de alta confianza (S_c > threshold)."""
        txs = await self.load_unreconciled_transactions(empresa_id=empresa_id)
        invs = await self.load_pending_invoices(empresa_id=empresa_id)
        matches, _, _ = self.find_best_candidates(
            transactions=txs,
            invoices=invs,
            threshold=threshold,
        )
        return {
            "threshold_used": threshold,
            "pending_transactions": len(txs),
            "pending_invoices": len(invs),
            "high_confidence_matches": [m.model_dump() for m in matches],
        }

    async def commit_matches(self, *, empresa_id: str, matches: list[ConciliationCandidate]) -> int:
        """Aplica conciliación en base de datos (estado cobrada / payment PAID)."""
        n = 0
        for m in matches:
            try:
                await self._commit_single_pair(empresa_id=empresa_id, m=m)
                n += 1
            except Exception as exc:
                _log.warning(
                    "matching_service: no se pudo conciliar tx=%s factura=%s: %s",
                    m.transaction_id,
                    m.factura_id,
                    exc,
                )
        return n

    async def _commit_single_pair(self, *, empresa_id: str, m: ConciliationCandidate) -> None:
        res_inv: Any = await self._db.execute(
            self._db.table("facturas")
            .select("id, empresa_id, total_factura")
            .eq("id", m.factura_id)
            .eq("empresa_id", empresa_id)
            .limit(1)
        )
        inv_rows = (res_inv.data or []) if hasattr(res_inv, "data") else []
        if not inv_rows:
            raise ValueError("Factura no encontrada")
        invoice = dict(inv_rows[0])

        res_tx: Any = await self._db.execute(
            self._db.table("bank_transactions")
            .select("*")
            .eq("transaction_id", m.transaction_id)
            .eq("empresa_id", empresa_id)
            .limit(1)
        )
        tx_rows = (res_tx.data or []) if hasattr(res_tx, "data") else []
        if not tx_rows:
            raise ValueError("Transacción no encontrada")
        tx = dict(tx_rows[0])

        fecha = tx.get("booked_date")
        fecha_cobro_real = (
            fecha.isoformat()[:10] if hasattr(fecha, "isoformat") else str(fecha or "")[:10]
        ) or date.today().isoformat()
        now_iso = datetime.now(timezone.utc).isoformat()

        await self._db.execute(
            self._db.table("facturas")
            .update(
                {
                    "estado_cobro": "cobrada",
                    "payment_status": "PAID",
                    "pago_id": m.transaction_id,
                    "matched_transaction_id": m.transaction_id,
                    "fecha_cobro_real": fecha_cobro_real,
                }
            )
            .eq("id", m.factura_id)
            .eq("empresa_id", empresa_id)
            .neq("estado_cobro", "cobrada")
        )
        await self._db.execute(
            self._db.table("bank_transactions")
            .update(
                {
                    "reconciled": True,
                    "internal_status": "reconciled",
                    "status_reconciled": "reconciled",
                    "updated_at": now_iso,
                }
            )
            .eq("empresa_id", empresa_id)
            .eq("transaction_id", m.transaction_id)
        )
        try:
            await AuditLogsService(self._db).log_bank_reconciliation(
                empresa_id=empresa_id,
                transaction_id=m.transaction_id,
                factura_id=int(m.factura_id),
                user_id=None,
            )
        except Exception:
            _log.warning(
                "matching_service: audit log conciliación omitido tx=%s factura=%s",
                m.transaction_id,
                m.factura_id,
                exc_info=True,
            )
        _ = invoice, tx

    async def auto_match(
        self,
        *,
        empresa_id: str,
        commit: bool = False,
        threshold: float = 0.85,
    ) -> dict[str, Any]:
        """
        Calcula sugerencias S_c > threshold; si ``commit`` aplica conciliación en bloque.
        """
        txs = await self.load_unreconciled_transactions(empresa_id=empresa_id)
        invs = await self.load_pending_invoices(empresa_id=empresa_id)
        matches, _, _ = self.find_best_candidates(
            transactions=txs,
            invoices=invs,
            threshold=threshold,
        )
        committed = 0
        if commit and matches:
            committed = await self.commit_matches(empresa_id=empresa_id, matches=matches)
        return {
            "threshold_used": threshold,
            "commit": commit,
            "suggestions": [m.model_dump() for m in matches],
            "committed_pairs": committed,
        }
