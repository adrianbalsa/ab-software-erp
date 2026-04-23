from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api import deps
from app.api.v1.webhooks import gocardless as wh


class _ExecResult:
    def __init__(self, data: list[dict[str, Any]] | None = None) -> None:
        self.data = data or []


class _EmpresasQuery:
    def __init__(self, db: "_FakeDb") -> None:
        self._db = db
        self._op = "select"
        self._filters: dict[str, Any] = {}
        self._payload: dict[str, Any] | None = None

    def select(self, _cols: str) -> "_EmpresasQuery":
        self._op = "select"
        return self

    def update(self, payload: dict[str, Any]) -> "_EmpresasQuery":
        self._op = "update"
        self._payload = dict(payload)
        return self

    def eq(self, key: str, value: Any) -> "_EmpresasQuery":
        self._filters[key] = value
        return self

    def limit(self, _n: int) -> "_EmpresasQuery":
        return self

    def execute(self) -> _ExecResult:
        if self._op == "select":
            eid = str(self._filters.get("id") or "")
            row = self._db.empresas_rows.get(eid)
            return _ExecResult([dict(row)] if row else [])
        if self._op == "update":
            eid = str(self._filters.get("id") or "")
            self._db.updated.append((eid, dict(self._payload or {})))
            if eid in self._db.empresas_rows:
                self._db.empresas_rows[eid].update(self._payload or {})
            return _ExecResult([])
        return _ExecResult([])


class _FakeDb:
    def __init__(self, empresas_rows: dict[str, dict[str, Any]] | None = None) -> None:
        self.empresas_rows = empresas_rows or {}
        self.updated: list[tuple[str, dict[str, Any]]] = []

    def table(self, name: str) -> _EmpresasQuery:
        if name != "empresas":
            raise AssertionError(f"Tabla no esperada en test: {name}")
        return _EmpresasQuery(self)

    async def execute(self, query: object) -> object:
        fn = getattr(query, "execute", None)
        if not callable(fn):
            raise TypeError("query sin execute()")
        return fn()


@pytest.mark.asyncio
async def test_process_billing_request_fulfilled_updates_empresa_and_sends_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empresa_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    db = _FakeDb(
        empresas_rows={
            empresa_id: {
                "id": empresa_id,
                "email": "ops@ab.test",
                "nombre_comercial": "AB Logistics",
                "nombre_legal": "AB Logistics Legal",
            }
        }
    )

    billing_request = SimpleNamespace(
        client_reference=empresa_id,
        links=SimpleNamespace(mandate="MD123", customer="CU456"),
    )
    gc_client = SimpleNamespace(
        billing_requests=SimpleNamespace(get=lambda _id: billing_request),
    )
    monkeypatch.setattr(wh, "_build_gocardless_client", lambda: gc_client)
    send_welcome = MagicMock(return_value=True)
    monkeypatch.setattr(
        wh.EmailService,
        "send_welcome_enterprise",
        lambda self, email, company: send_welcome(email, company),
    )

    await wh._process_billing_request_fulfilled(
        db=db,  # type: ignore[arg-type]
        event={"links": {"billing_request": "BR123"}},
    )

    assert db.updated == [
        (
            empresa_id,
            {"gocardless_mandate_id": "MD123", "gocardless_customer_id": "CU456"},
        )
    ]
    send_welcome.assert_called_once_with("ops@ab.test", "AB Logistics")


@pytest.mark.asyncio
async def test_process_billing_request_fulfilled_without_mandate_skips_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empresa_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    db = _FakeDb(
        empresas_rows={
            empresa_id: {
                "id": empresa_id,
                "email": "ops@ab.test",
                "nombre_comercial": "AB Logistics",
                "nombre_legal": "AB Logistics Legal",
            }
        }
    )

    billing_request = SimpleNamespace(
        client_reference=empresa_id,
        links=SimpleNamespace(mandate="", customer="CU456"),
    )
    gc_client = SimpleNamespace(
        billing_requests=SimpleNamespace(get=lambda _id: billing_request),
    )
    monkeypatch.setattr(wh, "_build_gocardless_client", lambda: gc_client)
    send_welcome = MagicMock(return_value=True)
    monkeypatch.setattr(
        wh.EmailService,
        "send_welcome_enterprise",
        lambda self, email, company: send_welcome(email, company),
    )

    await wh._process_billing_request_fulfilled(
        db=db,  # type: ignore[arg-type]
        event={"links": {"billing_request": "BR123"}},
    )

    assert db.updated == []
    send_welcome.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_listener_idempotency_skips_duplicate_event(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_db_admin] = lambda: _FakeDb()

    parse_out = SimpleNamespace(
        events=[
            {"id": "EV1", "resource_type": "billing_requests", "action": "fulfilled", "links": {"billing_request": "BR1"}},
            {"id": "EV1", "resource_type": "billing_requests", "action": "fulfilled", "links": {"billing_request": "BR1"}},
        ]
    )
    gc_mod = SimpleNamespace(Webhook=SimpleNamespace(parse=lambda *_a, **_k: parse_out))
    monkeypatch.setitem(sys.modules, "gocardless_pro", gc_mod)
    monkeypatch.setattr(wh, "claim_webhook_event", AsyncMock(side_effect=[True, False]))
    process = AsyncMock()
    monkeypatch.setattr(wh, "_process_billing_request_fulfilled", process)
    monkeypatch.setenv("GOCARDLESS_WEBHOOK_SECRET", "gcsec_test")

    try:
        res = await client.post(
            "/api/v1/webhooks/gocardless",
            content='{"events":[]}',
            headers={"Webhook-Signature": "sig"},
        )
        assert res.status_code == 204
        process.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhook_listener_rejects_invalid_signature(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_db_admin] = lambda: _FakeDb()
    bad_parse = SimpleNamespace(
        Webhook=SimpleNamespace(parse=lambda *_a, **_k: (_ for _ in ()).throw(ValueError("bad sig")))
    )
    monkeypatch.setitem(sys.modules, "gocardless_pro", bad_parse)
    monkeypatch.setenv("GOCARDLESS_WEBHOOK_SECRET", "gcsec_test")

    try:
        res = await client.post(
            "/api/v1/webhooks/gocardless",
            content='{"events":[]}',
            headers={"Webhook-Signature": "invalid"},
        )
        assert res.status_code == 401
        assert "inválida" in str(res.json().get("detail", "")).lower()
    finally:
        app.dependency_overrides.clear()
