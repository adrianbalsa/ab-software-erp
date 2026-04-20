"""
E2E — flujo bancario (API): pendientes de conciliación + fachada ``BankingService``.

Complementa ``test_banking_reconciliation_flow.py`` (orquestador híbrido + auditoría POST).
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import deps
from app.core.config import get_settings
from app.core.security import create_access_token
from app.main import create_app
from app.services.banking_service import BankingService
from app.services.secret_manager_service import reset_secret_manager
from tests.conftest import EMPRESA_A_ID
from tests.e2e.test_banking_reconciliation_flow import BankingReconciliationMemoryDb


@pytest.mark.asyncio
async def test_banking_pending_reconciliation_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/v1/banking/pending-reconciliation devuelve movimientos no conciliados con score fuzzy."""
    empresa_id = str(EMPRESA_A_ID)
    cliente_id = str(uuid4())
    tx_id = str(uuid4())
    mem = BankingReconciliationMemoryDb(
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        factura_id=7701,
        transaction_id=tx_id,
        invoice_number="FAC-2026-7701",
        bank_description="TRANSFER cobro FAC-2026-7701 cliente",
        invoice_total=Decimal("242.00"),
        booked_date="2026-04-10",
        fecha_emision="2026-04-01",
    )

    async def _get_db() -> BankingReconciliationMemoryDb:
        return mem

    async def _get_supabase(*_a: object, **_k: object) -> BankingReconciliationMemoryDb:
        return mem

    monkeypatch.setenv("GOCARDLESS_SECRET_ID", "sandbox_id")
    monkeypatch.setenv("GOCARDLESS_SECRET_KEY", "sandbox_key")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    reset_secret_manager()
    monkeypatch.setattr(
        "app.core.health_checks.run_deep_health",
        AsyncMock(
            return_value={
                "status": "healthy",
                "checks": {"supabase": {"ok": True}},
            },
        ),
    )
    monkeypatch.setattr("app.db.supabase.get_supabase", _get_supabase)
    monkeypatch.setattr("app.middleware.tenant_rbac_context.get_supabase", _get_supabase)
    monkeypatch.setattr("app.middleware.audit_log_middleware.get_supabase", _get_supabase)

    application = create_app()
    try:
        transport = ASGITransport(app=application, lifespan="on")
    except TypeError:
        transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app = client._transport.app  # type: ignore[attr-defined]
        app.dependency_overrides[deps.get_db] = _get_db
        try:
            bearer = create_access_token(subject="admin@qa.local", empresa_id=empresa_id)
            res = await client.get(
                "/api/v1/banking/pending-reconciliation",
                headers={"Authorization": f"Bearer {bearer}"},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert isinstance(body, list) and len(body) == 1
            row = body[0]
            assert row["transaction_id"] == tx_id
            assert row["ia_confidence"] > 0.5
            assert row["best_invoice_id"] == 7701
        finally:
            app.dependency_overrides.pop(deps.get_db, None)


def test_banking_service_wraps_gocardless_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOCARDLESS_SECRET_ID", "id_x")
    monkeypatch.setenv("GOCARDLESS_SECRET_KEY", "key_x")
    reset_secret_manager()
    svc = BankingService(MagicMock())
    assert svc.secrets_configured() is True
    diag = svc.secret_manager_diagnostics()
    assert diag["gocardless_secret_id_present"] is True
    assert diag["gocardless_secret_key_present"] is True

