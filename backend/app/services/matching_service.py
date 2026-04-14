"""
Motor de conciliación bancaria probabilística (importe exacto + fuzzy referencia + ventana de fechas).
"""
from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

from rapidfuzz import fuzz

from app.db.supabase import SupabaseAsync
from app.services.reconciliation_service import _tx_reference_blob

_log = logging.getLogger(__name__)


def _two_dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    except Exception:
        return Decimal("0.00")


def _invoice_number(row: dict[str, Any]) -> str:
    return str(row.get("numero_factura") or row.get("num_factura") or "").strip()


def _parse_iso_date(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()[:10]
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _fuzzy_text_score(blob: str, needle: str) -> float:
    """Combina RapidFuzz y difflib en [0, 1]."""
    b = (blob or "").strip().casefold()
    n = (needle or "").strip().casefold()
    if not b or not n:
        return 0.0
    r_fuzz = max(
        fuzz.token_set_ratio(b, n) / 100.0,
        fuzz.partial_ratio(b, n) / 100.0,
        fuzz.ratio(b, n) / 100.0,
    )
    r_diff = float(difflib.SequenceMatcher(None, b, n).ratio())
    return max(r_fuzz, r_diff)


def _reference_score(transaction: dict[str, Any], invoice: dict[str, Any]) -> float:
    blob = _tx_reference_blob(transaction)
    numero = _invoice_number(invoice)
    nombre = str(invoice.get("cliente_nombre") or "").strip()

    scores: list[float] = []
    if numero:
        if numero.casefold() in blob:
            scores.append(1.0)
        scores.append(_fuzzy_text_score(blob, numero))
    if nombre:
        scores.append(_fuzzy_text_score(blob, nombre))
    return max(scores) if scores else 0.0


def _date_alignment_score(tx_booked: date | None, inv_date: date | None) -> float:
    """
    Preferencia ±30 días: 1.0 mismo día, decae linealmente a 0 a los 30 días de diferencia.
    """
    if tx_booked is None or inv_date is None:
        return 0.5
    d = abs((tx_booked - inv_date).days)
    if d <= 30:
        return max(0.0, 1.0 - (d / 30.0))
    return 0.0


def combined_confidence_score(
    *,
    transaction: dict[str, Any],
    invoice: dict[str, Any],
    w_ref: float = 0.55,
    w_date: float = 0.45,
) -> float:
    """S_c: score global en [0, 1] (importe ya filtrado fuera)."""
    ref = _reference_score(transaction, invoice)
    txd = _parse_iso_date(transaction.get("booked_date"))
    invd = _parse_iso_date(invoice.get("fecha_emision"))
    dscore = _date_alignment_score(txd, invd)
    s = w_ref * ref + w_date * dscore
    return max(0.0, min(1.0, float(s)))


def _amount_matches_invoice(transaction: dict[str, Any], invoice: dict[str, Any]) -> bool:
    """Importe exacto (valor absoluto) en 2 decimales — cobros y pagos."""
    amt = _two_dec(transaction.get("amount"))
    tot = _two_dec(invoice.get("total_factura"))
    if tot <= 0:
        return False
    if amt == 0:
        return False
    return abs(amt) == abs(tot)


@dataclass
class MatchCandidate:
    transaction_id: str
    factura_id: int
    score: float
    reference_score: float
    date_score: float
    amount: float
    invoice_number: str | None
    booked_date: str | None
    invoice_date: str | None


class MatchingService:
    """Emparejamiento movimientos bancarios ↔ facturas pendientes de cobro/pago."""

    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def load_unreconciled_transactions(self, *, empresa_id: str) -> list[dict[str, Any]]:
        res: Any = await self._db.execute(
            self._db.table("bank_transactions")
            .select("*")
            .eq("empresa_id", empresa_id)
            .eq("reconciled", False)
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: list[dict[str, Any]] = []
        for r in rows:
            if _two_dec(r.get("amount")) == 0:
                continue
            tid = str(r.get("transaction_id") or "").strip()
            if not tid:
                continue
            out.append(dict(r))
        return out

    async def load_pending_invoices(self, *, empresa_id: str) -> list[dict[str, Any]]:
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
        out: list[dict[str, Any]] = []
        for r in rows:
            st = str(r.get("estado_cobro") or "").strip().lower()
            if st in ("cobrada", "pagada"):
                continue
            if _two_dec(r.get("total_factura")) <= 0:
                continue
            out.append(dict(r))
        return await self._enriquecer_nombres_cliente(empresa_id=empresa_id, facturas=out)

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
        transactions: list[dict[str, Any]],
        invoices: list[dict[str, Any]],
        threshold: float = 0.85,
    ) -> tuple[list[MatchCandidate], set[int], set[str]]:
        """
        Para cada movimiento, elige la factura con mayor S_c entre las de importe exacto;
        solo se acepta si S_c >= ``threshold``. Emparejamiento 1:1 (cada factura a lo sumo un movimiento).
        """
        inv_sorted = sorted(invoices, key=lambda x: int(x.get("id") or 0))
        tx_sorted = sorted(
            transactions,
            key=lambda t: str(t.get("transaction_id") or ""),
        )
        used_inv: set[int] = set()
        used_tx: set[str] = set()
        results: list[MatchCandidate] = []

        for tx in tx_sorted:
            tx_id = str(tx.get("transaction_id") or "").strip()
            if not tx_id or tx_id in used_tx:
                continue
            best_score = -1.0
            best_inv: dict[str, Any] | None = None
            for inv in inv_sorted:
                fid = int(inv.get("id") or 0)
                if fid in used_inv:
                    continue
                if not _amount_matches_invoice(tx, inv):
                    continue
                s_c = combined_confidence_score(transaction=tx, invoice=inv)
                if s_c > best_score:
                    best_score = s_c
                    best_inv = inv
            if best_inv is None or best_score < threshold:
                continue
            ref_s = _reference_score(tx, best_inv)
            txd = _parse_iso_date(tx.get("booked_date"))
            invd = _parse_iso_date(best_inv.get("fecha_emision"))
            dscore = _date_alignment_score(txd, invd)
            bd = tx.get("booked_date")
            booked_s = bd.isoformat()[:10] if hasattr(bd, "isoformat") else str(bd or "")[:10] or None
            fd = best_inv.get("fecha_emision")
            inv_s = fd.isoformat()[:10] if hasattr(fd, "isoformat") else str(fd or "")[:10] or None
            best = MatchCandidate(
                transaction_id=tx_id,
                factura_id=int(best_inv.get("id") or 0),
                score=round(best_score, 4),
                reference_score=round(ref_s, 4),
                date_score=round(dscore, 4),
                amount=float(_two_dec(tx.get("amount"))),
                invoice_number=_invoice_number(best_inv) or None,
                booked_date=booked_s,
                invoice_date=inv_s,
            )
            results.append(best)
            used_inv.add(best.factura_id)
            used_tx.add(best.transaction_id)

        return results, used_inv, used_tx

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
            "high_confidence_matches": [m.__dict__ for m in matches],
        }

    async def commit_matches(self, *, empresa_id: str, matches: list[MatchCandidate]) -> int:
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

    async def _commit_single_pair(self, *, empresa_id: str, m: MatchCandidate) -> None:
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
                    "updated_at": now_iso,
                }
            )
            .eq("empresa_id", empresa_id)
            .eq("transaction_id", m.transaction_id)
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
            "suggestions": [m.__dict__ for m in matches],
            "committed_pairs": committed,
        }
