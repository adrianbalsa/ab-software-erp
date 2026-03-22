"""Conciliación bancaria: importe exacto positivo + número de factura en concepto."""

from app.services.reconciliation_service import match_unreconciled_to_invoices


def test_match_amount_and_invoice_number_in_description():
    bank_rows = [
        {
            "transaction_id": "tx-1",
            "amount": 121.0,
            "description": "Transferencia FAC-2026-000042 cliente ACME",
            "booked_date": "2026-03-10",
            "reconciled": False,
        }
    ]
    facs = [
        {
            "id": 10,
            "numero_factura": "FAC-2026-000042",
            "total_factura": 121.0,
            "estado_cobro": "emitida",
        }
    ]
    pairs = match_unreconciled_to_invoices(bank_rows=bank_rows, facturas_emitidas=facs)
    assert len(pairs) == 1
    assert pairs[0]["factura_id"] == 10
    assert pairs[0]["transaction_id"] == "tx-1"


def test_case_insensitive_invoice_number():
    bank_rows = [
        {
            "transaction_id": "tx-2",
            "amount": 50.0,
            "description": "pago factura fac-2026-99",
            "booked_date": "2026-03-01",
            "reconciled": False,
        }
    ]
    facs = [
        {
            "id": 1,
            "numero_factura": "FAC-2026-99",
            "total_factura": 50.0,
            "estado_cobro": "emitida",
        }
    ]
    pairs = match_unreconciled_to_invoices(bank_rows=bank_rows, facturas_emitidas=facs)
    assert len(pairs) == 1


def test_no_match_negative_amount_excluded():
    bank_rows = [
        {
            "transaction_id": "tx-3",
            "amount": -100.50,
            "description": "FAC-2026-001",
            "booked_date": "2026-02-15",
            "reconciled": False,
        }
    ]
    facs = [
        {
            "id": 2,
            "numero_factura": "FAC-2026-001",
            "total_factura": 100.50,
            "estado_cobro": "emitida",
        }
    ]
    pairs = match_unreconciled_to_invoices(bank_rows=bank_rows, facturas_emitidas=facs)
    assert pairs == []


def test_no_match_wrong_amount():
    bank_rows = [
        {
            "transaction_id": "tx-4",
            "amount": 100.0,
            "description": "FAC-2026-001",
            "booked_date": "2026-02-15",
            "reconciled": False,
        }
    ]
    facs = [
        {
            "id": 2,
            "numero_factura": "FAC-2026-001",
            "total_factura": 100.50,
            "estado_cobro": "emitida",
        }
    ]
    pairs = match_unreconciled_to_invoices(bank_rows=bank_rows, facturas_emitidas=facs)
    assert pairs == []


def test_no_match_missing_number_in_description():
    bank_rows = [
        {
            "transaction_id": "tx-5",
            "amount": 200.0,
            "description": "Transferencia genérica sin referencia",
            "booked_date": "2026-02-15",
            "reconciled": False,
        }
    ]
    facs = [
        {
            "id": 3,
            "numero_factura": "FAC-2026-200",
            "total_factura": 200.0,
            "estado_cobro": "emitida",
        }
    ]
    pairs = match_unreconciled_to_invoices(bank_rows=bank_rows, facturas_emitidas=facs)
    assert pairs == []
