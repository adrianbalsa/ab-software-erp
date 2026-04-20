"""
E2E de dominio — Webhooks Stripe → ``empresas.is_active`` / ``subscription_status``.

Simula ``invoice.payment_failed`` (firma vía SDK mockeado) y comprueba bloqueo en
``assert_empresa_billing_active``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.services import stripe_service
from app.services.secret_manager_service import reset_secret_manager
from tests.conftest import EMPRESA_A_ID


class _ExecResult:
    __slots__ = ("data",)

    def __init__(self, data: list[dict[str, Any]] | None = None) -> None:
        self.data = data or []


class _EmpresaSelect:
    def __init__(self, store: dict[str, dict[str, Any]], _cols: str) -> None:
        self._store = store
        self._filters: dict[str, str] = {}

    def eq(self, key: str, value: Any) -> _EmpresaSelect:
        self._filters[key] = str(value)
        return self

    def limit(self, _n: int) -> _EmpresaSelect:
        return self

    def execute(self) -> _ExecResult:
        rows: list[dict[str, Any]] = []
        for r in self._store.values():
            if all(str(r.get(k)) == v for k, v in self._filters.items()):
                rows.append(dict(r))
        return _ExecResult(rows[:1])


class _EmpresaUpdate:
    def __init__(self, store: dict[str, dict[str, Any]], payload: dict[str, Any]) -> None:
        self._store = store
        self._payload = payload
        self._filters: dict[str, str] = {}

    def eq(self, key: str, value: Any) -> _EmpresaUpdate:
        self._filters[key] = str(value)
        return self

    def execute(self) -> _ExecResult:
        for r in self._store.values():
            if all(str(r.get(k)) == v for k, v in self._filters.items()):
                r.update(self._payload)
        return _ExecResult()


class _EmpresaTable:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self._store = store

    def select(self, cols: str = "*") -> _EmpresaSelect:
        return _EmpresaSelect(self._store, cols)

    def update(self, payload: dict[str, Any]) -> _EmpresaUpdate:
        return _EmpresaUpdate(self._store, payload)


class _StripeWebhookE2eDb:
    """Solo ``empresas``; idempotencia Stripe va mockeada."""

    def __init__(self, empresas: dict[str, dict[str, Any]]) -> None:
        self._empresas = empresas

    def table(self, name: str) -> _EmpresaTable:
        if name == "empresas":
            return _EmpresaTable(self._empresas)
        raise AssertionError(f"tabla no soportada: {name}")

    async def execute(self, query: object) -> object:
        fn = getattr(query, "execute", None)
        if not callable(fn):
            raise TypeError("query debe exponer execute()")
        return fn()


@pytest.mark.asyncio
async def test_invoice_payment_failed_blocks_empresa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
    reset_secret_manager()

    eid = str(EMPRESA_A_ID)
    empresas: dict[str, dict[str, Any]] = {
        eid: {
            "id": eid,
            "deleted_at": None,
            "stripe_customer_id": "cus_test_block",
            "stripe_subscription_id": "sub_test_block",
            "is_active": True,
            "subscription_status": "active",
        }
    }
    db = _StripeWebhookE2eDb(empresas)

    monkeypatch.setattr(stripe_service, "claim_webhook_event", AsyncMock(return_value=True))
    monkeypatch.setattr(stripe_service, "finalize_stripe_webhook_claim", AsyncMock())
    monkeypatch.setattr(stripe_service, "release_stripe_webhook_claim", AsyncMock())

    def _fake_construct(_payload: bytes, _sig: str, _secret: str) -> dict[str, Any]:
        return {
            "id": "evt_payfail_1",
            "type": "invoice.payment_failed",
            "data": {"object": {"customer": "cus_test_block"}},
        }

    monkeypatch.setattr(
        stripe_service.stripe.Webhook,
        "construct_event",
        staticmethod(_fake_construct),
    )

    await stripe_service.handle_webhook(
        payload=b"{}",
        sig_header="t=0,v1=ignored",
        db=db,  # type: ignore[arg-type]
    )

    row = empresas[eid]
    assert row["is_active"] is False
    assert row["subscription_status"] == "past_due"

    with pytest.raises(HTTPException) as exc:
        await stripe_service.assert_empresa_billing_active(db, empresa_id=eid)  # type: ignore[arg-type]
    assert exc.value.status_code == 403

    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    reset_secret_manager()
