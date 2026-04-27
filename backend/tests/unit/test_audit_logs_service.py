from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.services.audit_logs_service import AuditLogsService, pseudonymize_audit_payload


@dataclass
class _FakeResult:
    data: list[dict[str, Any]] | None = None


class _FakeDb:
    def __init__(self) -> None:
        self.rpc_name: str | None = None
        self.rpc_params: dict[str, Any] | None = None

    async def rpc(self, fn: str, params: dict[str, Any] | None = None) -> _FakeResult:
        self.rpc_name = fn
        self.rpc_params = dict(params or {})
        return _FakeResult(data=[{"id": "00000000-0000-4000-8000-000000000001"}])


def test_pseudonymize_audit_payload_export_masks_actor_email() -> None:
    out = pseudonymize_audit_payload({"actor": "ops@example.com", "secret_kind": "pii"})
    assert "ops@example.com" not in str(out)
    assert str(out["actor"]).startswith("o***s@")
    assert out["secret_kind"] == "pii"


@pytest.mark.asyncio
async def test_log_sensitive_action_pseudonymizes_nif() -> None:
    db = _FakeDb()
    await AuditLogsService(db).log_sensitive_action(
        empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        table_name="clientes",
        record_id="cliente-1",
        action="UPDATE",
        new_value={"nif": "B12345678"},
    )

    assert db.rpc_name == "audit_logs_insert_api_event"
    assert db.rpc_params is not None
    payload = db.rpc_params["p_new_data"]
    assert payload["nif"].startswith("B***78#sha256:")
    assert "B12345678" not in str(payload)


@pytest.mark.asyncio
async def test_log_sensitive_action_pseudonymizes_email() -> None:
    db = _FakeDb()
    await AuditLogsService(db).log_sensitive_action(
        empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        table_name="clientes",
        record_id="cliente-1",
        action="INVITE_SENT",
        new_value={"invite_email": "ada.lovelace@example.com"},
    )

    assert db.rpc_params is not None
    payload = db.rpc_params["p_new_data"]
    assert payload["invite_email"].startswith("a***e@example.com#sha256:")
    assert "ada.lovelace@example.com" not in str(payload)


@pytest.mark.asyncio
async def test_log_sensitive_action_pseudonymizes_name_like_fields() -> None:
    db = _FakeDb()
    await AuditLogsService(db).log_sensitive_action(
        empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        table_name="clientes",
        record_id="cliente-1",
        action="UPDATE",
        new_value={"nombre_cliente": "Ada Lovelace"},
    )

    assert db.rpc_params is not None
    payload = db.rpc_params["p_new_data"]
    assert payload["nombre_cliente"].startswith("A***ace#sha256:")
    assert "Ada Lovelace" not in str(payload)


@pytest.mark.asyncio
async def test_log_sensitive_action_pseudonymizes_mixed_payloads_recursively() -> None:
    db = _FakeDb()
    await AuditLogsService(db).log_sensitive_action(
        empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        table_name="api_requests",
        record_id="/api/v1/clientes",
        action="UPDATE",
        old_value={"status": "pending", "contact": "Cliente B12345678 <ops@example.com>"},
        new_value={
            "extension_correo": {
                "destinatarios": ["ops@example.com", "billing@example.com"],
                "notas": "Revisar NIF B12345678 antes de reenviar",
            },
            "limite_credito": 3500,
            "tags": ["vip", {"email_secundario": "owner@example.com"}],
        },
    )

    assert db.rpc_params is not None
    old_payload = db.rpc_params["p_old_data"]
    new_payload = db.rpc_params["p_new_data"]
    combined = f"{old_payload} {new_payload}"

    assert "B12345678" not in combined
    assert "ops@example.com" not in combined
    assert "billing@example.com" not in combined
    assert "owner@example.com" not in combined
    assert old_payload["status"] == "pending"
    assert new_payload["limite_credito"] == 3500
    assert "sha256:" in combined
