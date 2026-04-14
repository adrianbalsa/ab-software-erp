"""
Cálculo aislado de similitud de texto (RapidFuzz + difflib) y puntuaciones de conciliación.
Extraído para pruebas unitarias sin base de datos.
"""

from __future__ import annotations

import difflib
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from rapidfuzz import fuzz

from app.schemas.banking import FacturaConciliacion, Transaccion


def two_dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    except Exception:
        return Decimal("0.00")


def parse_iso_date(val: Any) -> date | None:
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


def fuzzy_text_score(blob: str, needle: str) -> float:
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


def reference_score(transaction: Transaccion, invoice: FacturaConciliacion) -> float:
    blob = transaction.reference_blob()
    numero = invoice.invoice_number()
    nombre = str(invoice.cliente_nombre or "").strip()

    scores: list[float] = []
    if numero:
        if numero.casefold() in blob:
            scores.append(1.0)
        scores.append(fuzzy_text_score(blob, numero))
    if nombre:
        scores.append(fuzzy_text_score(blob, nombre))
    return max(scores) if scores else 0.0


def date_alignment_score(tx_booked: date | None, inv_date: date | None) -> float:
    """Preferencia ±30 días: 1.0 mismo día, decae linealmente a 0 a los 30 días."""
    if tx_booked is None or inv_date is None:
        return 0.5
    d = abs((tx_booked - inv_date).days)
    if d <= 30:
        return max(0.0, 1.0 - (d / 30.0))
    return 0.0


def combined_confidence_score(
    *,
    transaction: Transaccion,
    invoice: FacturaConciliacion,
    w_ref: float = 0.55,
    w_date: float = 0.45,
) -> float:
    """S_c: score global en [0, 1] (importe ya filtrado fuera)."""
    ref = reference_score(transaction, invoice)
    txd = parse_iso_date(transaction.booked_date)
    invd = parse_iso_date(invoice.fecha_emision)
    dscore = date_alignment_score(txd, invd)
    s = w_ref * ref + w_date * dscore
    return max(0.0, min(1.0, float(s)))


def amount_matches_invoice(transaction: Transaccion, invoice: FacturaConciliacion) -> bool:
    """Importe exacto (valor absoluto) en 2 decimales — cobros y pagos."""
    amt = two_dec(transaction.amount)
    tot = two_dec(invoice.total_factura)
    if tot <= 0:
        return False
    if amt == 0:
        return False
    return abs(amt) == abs(tot)
