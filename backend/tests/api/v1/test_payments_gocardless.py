from __future__ import annotations

import sys
from uuid import UUID
from unittest.mock import MagicMock

import pytest

# Dependencias opcionales cargadas por imports transversales de app.api.deps
sys.modules.setdefault("azure", MagicMock(name="azure_test_double"))
sys.modules.setdefault("azure.ai", MagicMock(name="azure_ai_test_double"))
sys.modules.setdefault(
    "azure.ai.formrecognizer",
    MagicMock(name="azure_formrecognizer_test_double"),
)
sys.modules.setdefault(
    "azure.ai.formrecognizer.aio",
    MagicMock(name="azure_formrecognizer_aio_test_double"),
)
sys.modules.setdefault("azure.core", MagicMock(name="azure_core_test_double"))
sys.modules.setdefault("azure.core.credentials", MagicMock(name="azure_core_credentials_test_double"))

from app.api import deps
from app.schemas.user import UserOut
from app.services.payment_service import PaymentDomainError, PaymentIntegrationError


def _user_with_role(role: str) -> UserOut:
    return UserOut(
        username="qa@test.local",
        empresa_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        rol="user",
        rbac_role=role,
        usuario_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    )


@pytest.mark.asyncio
async def test_security_non_privileged_role_gets_403(client) -> None:
    class _MockPaymentService:
        async def create_one_off_payment_from_invoice(self, **_kwargs):
            return {}

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_payment_service] = lambda: _MockPaymentService()
    app.dependency_overrides[deps.get_current_user] = lambda: _user_with_role("driver")
    app.dependency_overrides[deps.bind_write_context] = lambda: _user_with_role("driver")

    try:
        res = await client.post(
            "/api/v1/payments/gocardless/one-off",
            json={
                "factura_id": 10,
                "customer_id": "CU123",
                "mandate_id": "MD123",
                "currency": "EUR",
            },
        )
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_customer_success_returns_payload(client) -> None:
    class _MockPaymentService:
        async def create_customer(self, **_kwargs):
            return {
                "customer_id": "CU999",
                "empresa_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "created_at": "2026-03-26T12:00:00+00:00",
            }

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_payment_service] = lambda: _MockPaymentService()
    app.dependency_overrides[deps.get_current_user] = lambda: _user_with_role("owner")
    app.dependency_overrides[deps.bind_write_context] = lambda: _user_with_role("owner")

    try:
        res = await client.post(
            "/api/v1/payments/gocardless/customers",
            json={
                "given_name": "Ada",
                "family_name": "Lovelace",
                "email": "ada@example.com",
            },
        )
        assert res.status_code in (200, 201)
        body = res.json()
        assert body["customer_id"] == "CU999"
        assert body["empresa_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_integration_error_maps_to_502(client) -> None:
    class _MockPaymentService:
        async def create_one_off_payment_from_invoice(self, **_kwargs):
            raise PaymentIntegrationError("upstream timeout")

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_payment_service] = lambda: _MockPaymentService()
    app.dependency_overrides[deps.get_current_user] = lambda: _user_with_role("traffic_manager")
    app.dependency_overrides[deps.bind_write_context] = lambda: _user_with_role("traffic_manager")

    try:
        res = await client.post(
            "/api/v1/payments/gocardless/one-off",
            json={
                "factura_id": 11,
                "customer_id": "CU11",
                "mandate_id": "MD11",
                "currency": "EUR",
            },
        )
        assert res.status_code == 502
        assert "upstream timeout" in str(res.json().get("detail", ""))
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_nonexistent_invoice_maps_to_validation_error(client) -> None:
    class _MockPaymentService:
        async def create_one_off_payment_from_invoice(self, **_kwargs):
            raise PaymentDomainError("Factura no encontrada para la empresa.")

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_payment_service] = lambda: _MockPaymentService()
    app.dependency_overrides[deps.get_current_user] = lambda: _user_with_role("owner")
    app.dependency_overrides[deps.bind_write_context] = lambda: _user_with_role("owner")

    try:
        res = await client.post(
            "/api/v1/payments/gocardless/one-off",
            json={
                "factura_id": 999999,
                "customer_id": "CU404",
                "mandate_id": "MD404",
                "currency": "EUR",
            },
        )
        assert res.status_code in (400, 404)
    finally:
        app.dependency_overrides.clear()

