from __future__ import annotations

from uuid import UUID

import pytest

from app.api import deps
from app.api.v1 import banking as banking_v1
from app.core.math_engine import MathEngine
from app.models.enums import UserRole
from app.schemas.user import UserOut


def _admin_user() -> UserOut:
    return UserOut(
        username="owner@test.local",
        empresa_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        role=UserRole.ADMIN,
        rol="admin",
        rbac_role="owner",
        usuario_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    )


class _MockBankingService:
    async def get_institutions(self, *, country_code: str = "ES"):
        assert country_code == "ES"
        return [
            {
                "id": "bbva-es",
                "name": "BBVA",
                "bic": "BBVAESMM",
                "transaction_total_days": "730",
                "countries": ["ES"],
            }
        ]

    async def create_requisition(self, *, empresa_id: str, institution_id: str, redirect_url: str | None = None):
        assert empresa_id == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        assert institution_id == "bbva-es"
        return {"link": "https://consent.example", "requisition_id": "REQ123"}

    async def sincronizar_y_conciliar(self, *, empresa_id: str, date_from=None, date_to=None):
        assert empresa_id == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        class _R:
            transacciones_procesadas = 3
            coincidencias = 2
            detalle = [{"factura_id": 1, "transaction_id": "tx-1"}]

        return _R()


@pytest.mark.asyncio
async def test_get_banking_institutions(client, monkeypatch: pytest.MonkeyPatch) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_banking_service] = lambda: _MockBankingService()
    app.dependency_overrides[deps.require_admin_active_write_user] = lambda: _admin_user()
    monkeypatch.setattr(banking_v1, "_gocardless_configured", lambda: True)
    try:
        res = await client.get("/api/v1/banking/institutions?country_code=ES")
        assert res.status_code == 200, res.text
        body = res.json()
        assert isinstance(body, list) and len(body) == 1
        assert body[0]["id"] == "bbva-es"
        assert body[0]["name"] == "BBVA"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_banking_connect(client, monkeypatch: pytest.MonkeyPatch) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_banking_service] = lambda: _MockBankingService()
    app.dependency_overrides[deps.require_admin_active_write_user] = lambda: _admin_user()
    monkeypatch.setattr(banking_v1, "_gocardless_configured", lambda: True)
    try:
        res = await client.post("/api/v1/banking/connect", json={"institution_id": "bbva-es"})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["requisition_id"] == "REQ123"
        assert "consent.example" in body["link"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_banking_sync_alias(client, monkeypatch: pytest.MonkeyPatch) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_banking_service] = lambda: _MockBankingService()
    app.dependency_overrides[deps.require_admin_active_write_user] = lambda: _admin_user()
    monkeypatch.setattr(banking_v1, "_gocardless_configured", lambda: True)
    try:
        res = await client.get("/api/v1/banking/sync")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["transacciones_procesadas"] == 3
        assert body["coincidencias"] == 2
    finally:
        app.dependency_overrides.clear()


def test_math_engine_match_transactions_to_invoices_exact_and_date_window() -> None:
    matches = MathEngine.match_transactions_to_invoices(
        transactions=[
            {"transaction_id": "tx-100", "amount": "242.00", "booked_date": "2026-04-10"},
            {"transaction_id": "tx-200", "amount": "300.00", "booked_date": "2026-04-10"},
        ],
        pending_invoices=[
            {"id": 1, "total_factura": "242.00", "fecha_emision": "2026-04-08"},
            {"id": 2, "total_factura": "300.00", "fecha_emision": "2026-03-01"},
        ],
        date_tolerance_days=3,
    )
    assert matches == [{"transaction_id": "tx-100", "factura_id": 1}]


def test_math_engine_match_transactions_to_invoices_uses_invoice_once() -> None:
    matches = MathEngine.match_transactions_to_invoices(
        transactions=[
            {"transaction_id": "tx-a", "amount": "50.00", "booked_date": "2026-04-10"},
            {"transaction_id": "tx-b", "amount": "50.00", "booked_date": "2026-04-10"},
        ],
        pending_invoices=[
            {"id": 11, "total_factura": "50.00", "fecha_emision": "2026-04-09"},
        ],
        date_tolerance_days=3,
    )
    assert len(matches) == 1
    assert matches[0]["factura_id"] == 11
