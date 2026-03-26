from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.services.payment_service import (
    PaymentDomainError,
    PaymentIntegrationError,
    PaymentService,
)


@dataclass
class _FakeResult:
    data: list[dict[str, Any]] | None = None


class _FakeQuery:
    def __init__(self, table: str, action: str = "select", payload: dict[str, Any] | None = None) -> None:
        self.table = table
        self.action = action
        self.payload = payload or {}
        self.filters: dict[str, Any] = {}

    def select(self, *_args: object) -> _FakeQuery:
        self.action = "select"
        return self

    def update(self, payload: dict[str, Any]) -> _FakeQuery:
        self.action = "update"
        self.payload = payload
        return self

    def insert(self, payload: dict[str, Any]) -> _FakeQuery:
        self.action = "insert"
        self.payload = payload
        return self

    def eq(self, key: str, value: Any) -> _FakeQuery:
        self.filters[key] = value
        return self

    def limit(self, *_args: object) -> _FakeQuery:
        return self


class _FakeDb:
    def __init__(self, invoice_row: dict[str, Any] | None) -> None:
        self.invoice_row = invoice_row
        self.updated_factura: dict[str, Any] | None = None
        self.audit_payload: dict[str, Any] | None = None

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(name)

    async def execute(self, query: _FakeQuery) -> _FakeResult:
        if query.table == "facturas" and query.action == "select":
            if self.invoice_row is None:
                return _FakeResult(data=[])
            return _FakeResult(data=[self.invoice_row])
        if query.table == "facturas" and query.action == "update":
            self.updated_factura = query.payload
            if self.invoice_row is not None:
                self.invoice_row.update(query.payload)
            return _FakeResult(data=[self.invoice_row] if self.invoice_row else [])
        if query.table == "audit_logs" and query.action == "insert":
            self.audit_payload = query.payload
            return _FakeResult(data=[query.payload])
        return _FakeResult(data=[])


class _FakeEntity:
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeCustomers:
    def create(self, *, params: dict[str, Any]) -> _FakeEntity:
        assert params["given_name"] == "Ada"
        return _FakeEntity(id="CU123")


class _FakePayments:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.last_params: dict[str, Any] | None = None
        self.last_headers: dict[str, Any] | None = None

    def create(self, *, params: dict[str, Any], headers: dict[str, Any]) -> _FakeEntity:
        if self.should_fail:
            raise RuntimeError("external 502")
        self.last_params = params
        self.last_headers = headers
        return _FakeEntity(id="PM999", status="pending_submission")


class _FakeGcClient:
    def __init__(self, should_fail_payment: bool = False) -> None:
        self.customers = _FakeCustomers()
        self.payments = _FakePayments(should_fail=should_fail_payment)


@pytest.mark.asyncio
async def test_create_customer_success() -> None:
    db = _FakeDb(invoice_row=None)
    svc = PaymentService(db=db, gc_client=_FakeGcClient())
    out = await svc.create_customer(
        empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        given_name="Ada",
        family_name="Lovelace",
        email="ada@example.com",
    )
    assert out["customer_id"] == "CU123"


@pytest.mark.asyncio
async def test_create_one_off_payment_from_invoice_success() -> None:
    db = _FakeDb(
        invoice_row={
            "id": 12,
            "empresa_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "total_factura": "123.45",
            "estado_cobro": "emitida",
            "pago_id": None,
        }
    )
    gc = _FakeGcClient()
    svc = PaymentService(db=db, gc_client=gc)
    out = await svc.create_one_off_payment_from_invoice(
        empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        factura_id=12,
        customer_id="CU123",
        mandate_id="MD123",
    )
    assert out["payment_id"] == "PM999"
    assert gc.payments.last_params is not None
    assert gc.payments.last_params["amount"] == 12345
    assert db.updated_factura is not None
    assert db.audit_payload is not None


@pytest.mark.asyncio
async def test_create_one_off_payment_fails_when_invoice_already_paid() -> None:
    db = _FakeDb(
        invoice_row={
            "id": 12,
            "empresa_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "total_factura": "123.45",
            "estado_cobro": "cobrada",
            "pago_id": "gocardless:old",
        }
    )
    svc = PaymentService(db=db, gc_client=_FakeGcClient())
    with pytest.raises(PaymentDomainError):
        await svc.create_one_off_payment_from_invoice(
            empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            factura_id=12,
            customer_id="CU123",
            mandate_id="MD123",
        )


@pytest.mark.asyncio
async def test_create_one_off_payment_maps_external_error() -> None:
    db = _FakeDb(
        invoice_row={
            "id": 12,
            "empresa_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "total_factura": "123.45",
            "estado_cobro": "emitida",
            "pago_id": None,
        }
    )
    svc = PaymentService(db=db, gc_client=_FakeGcClient(should_fail_payment=True))
    with pytest.raises(PaymentIntegrationError):
        await svc.create_one_off_payment_from_invoice(
            empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            factura_id=12,
            customer_id="CU123",
            mandate_id="MD123",
        )

