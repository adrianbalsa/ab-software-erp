from __future__ import annotations

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ``secret_manager_service`` importa ``hvac`` en tiempo de carga.
_hvac = MagicMock()
_exc = MagicMock()


class _Forbidden(Exception):
    pass


_exc.Forbidden = _Forbidden
_hvac.exceptions = _exc
sys.modules.setdefault("hvac", _hvac)
sys.modules.setdefault("hvac.exceptions", _exc)

from app.services import stripe_service
from app.services.webhook_idempotency import (
    _is_unique_violation,
    claim_webhook_event,
    finalize_stripe_webhook_claim,
    release_stripe_webhook_claim,
)


class _ExecResult:
    data: list[Any] = []


class _FakeTable:
    def __init__(self, db: "_FakeSupabase", name: str) -> None:
        self._db = db
        self._name = name

    def insert(self, data: dict[str, Any]) -> "_FakeInsert":
        return _FakeInsert(self._db, self._name, data)

    def update(self, data: dict[str, Any]) -> "_FakeUpdate":
        return _FakeUpdate(self._db, self._name, data)

    def delete(self) -> "_FakeDelete":
        return _FakeDelete(self._db, self._name)


class _FakeInsert:
    def __init__(self, db: "_FakeSupabase", table: str, data: dict[str, Any]) -> None:
        self._db = db
        self._table = table
        self._data = data

    def execute(self) -> _ExecResult:
        if self._table == "webhook_events":
            ext = str(self._data.get("external_event_id") or "").strip()
            if ext:
                key = (str(self._data.get("provider") or ""), ext)
                if key in self._db._webhook_keys:
                    raise Exception(
                        'duplicate key value violates unique constraint "idx_webhook_events_provider_external_event_id"'
                    )
                self._db._webhook_keys.add(key)
        return _ExecResult()


class _FakeUpdate:
    def __init__(self, db: "_FakeSupabase", table: str, data: dict[str, Any]) -> None:
        self._db = db
        self._table = table
        self._data = data

    def eq(self, *_a: object, **_k: object) -> "_FakeUpdate":
        return self

    def execute(self) -> _ExecResult:
        self._db._updates.append((self._table, self._data))
        return _ExecResult()


class _FakeDelete:
    def __init__(self, db: "_FakeSupabase", table: str) -> None:
        self._db = db
        self._table = table

    def eq(self, *_a: object, **_k: object) -> "_FakeDelete":
        return self

    def execute(self) -> _ExecResult:
        self._db._deletes += 1
        return _ExecResult()


class _FakeSupabase:
    """Mínimo para ``claim_webhook_event`` / finalize / release."""

    def __init__(self) -> None:
        self._webhook_keys: set[tuple[str, str]] = set()
        self._updates: list[tuple[str, dict[str, Any]]] = []
        self._deletes = 0

    def table(self, name: str) -> _FakeTable:
        return _FakeTable(self, name)

    async def execute(self, query: object) -> object:
        fn = getattr(query, "execute", None)
        if callable(fn):
            return fn()
        raise TypeError("expected query with execute()")


def test_is_unique_violation_detects_postgres_message() -> None:
    assert _is_unique_violation(Exception('duplicate key value violates unique constraint "u"'))


def test_is_unique_violation_false_on_other_errors() -> None:
    assert not _is_unique_violation(Exception("connection reset"))


@pytest.mark.asyncio
async def test_claim_webhook_event_first_insert_then_duplicate() -> None:
    db = _FakeSupabase()
    assert await claim_webhook_event(
        db,  # type: ignore[arg-type]
        provider="gocardless",
        external_event_id="EV123",
        event_type="payments.confirmed",
        payload={"id": "EV123"},
        status="PENDING",
    )
    assert not await claim_webhook_event(
        db,  # type: ignore[arg-type]
        provider="gocardless",
        external_event_id="EV123",
        event_type="payments.confirmed",
        payload={"id": "EV123"},
        status="PENDING",
    )


@pytest.mark.asyncio
async def test_claim_webhook_event_empty_external_skips_dedupe() -> None:
    db = _FakeSupabase()
    assert await claim_webhook_event(
        db,  # type: ignore[arg-type]
        provider="stripe",
        external_event_id="   ",
        event_type="x",
        payload={},
        status="PENDING",
    )
    assert db._webhook_keys == set()


@pytest.mark.asyncio
async def test_finalize_and_release_stripe_claim() -> None:
    db = _FakeSupabase()
    assert await claim_webhook_event(
        db,  # type: ignore[arg-type]
        provider="stripe",
        external_event_id="evt_abc",
        event_type="invoice.paid",
        payload={"id": "evt_abc"},
        status="PROCESSING",
    )
    await finalize_stripe_webhook_claim(db, external_event_id="evt_abc")  # type: ignore[arg-type]
    assert db._updates
    await release_stripe_webhook_claim(db, external_event_id="evt_abc")  # type: ignore[arg-type]
    assert db._deletes == 1


@pytest.mark.asyncio
async def test_stripe_handle_webhook_duplicate_claim_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    import stripe as stripe_mod

    monkeypatch.setattr(
        stripe_mod.Webhook,
        "construct_event",
        lambda *a, **k: {"id": "evt_dup_test", "type": "invoice.paid", "data": {"object": {}}},
    )
    monkeypatch.setattr(stripe_service, "claim_webhook_event", AsyncMock(return_value=False))

    db = MagicMock()
    db.execute = AsyncMock()
    out = await stripe_service.handle_webhook(payload=b"{}", sig_header="sig", db=db)
    assert out == {"received": True, "duplicate": True, "event_id": "evt_dup_test"}
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_stripe_handle_webhook_success_calls_finalize(monkeypatch: pytest.MonkeyPatch) -> None:
    import stripe as stripe_mod

    monkeypatch.setattr(
        stripe_mod.Webhook,
        "construct_event",
        lambda *a, **k: {"id": "evt_ok", "type": "invoice.paid", "data": {"object": {}}},
    )
    monkeypatch.setattr(stripe_service, "claim_webhook_event", AsyncMock(return_value=True))
    finalize = AsyncMock()
    monkeypatch.setattr(stripe_service, "finalize_stripe_webhook_claim", finalize)
    monkeypatch.setattr(
        stripe_service,
        "_dispatch_stripe_webhook_event",
        AsyncMock(return_value={"received": True, "event": "invoice.paid"}),
    )

    db = MagicMock()
    db.execute = AsyncMock()
    out = await stripe_service.handle_webhook(payload=b"{}", sig_header="sig", db=db)
    assert out["received"] is True
    finalize.assert_awaited_once_with(db, external_event_id="evt_ok")


@pytest.mark.asyncio
async def test_stripe_handle_webhook_dispatch_error_releases_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    import stripe as stripe_mod

    monkeypatch.setattr(
        stripe_mod.Webhook,
        "construct_event",
        lambda *a, **k: {"id": "evt_fail", "type": "invoice.paid", "data": {"object": {}}},
    )
    monkeypatch.setattr(stripe_service, "claim_webhook_event", AsyncMock(return_value=True))
    release = AsyncMock()
    monkeypatch.setattr(stripe_service, "release_stripe_webhook_claim", release)
    monkeypatch.setattr(
        stripe_service,
        "_dispatch_stripe_webhook_event",
        AsyncMock(side_effect=RuntimeError("downstream")),
    )

    db = MagicMock()
    with pytest.raises(RuntimeError, match="downstream"):
        await stripe_service.handle_webhook(payload=b"{}", sig_header="sig", db=db)
    release.assert_awaited_once_with(db, external_event_id="evt_fail")


@pytest.mark.asyncio
async def test_gocardless_process_skips_second_identical_event_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1 import webhooks_gocardless as wh
    from app.services import reconciliation_service

    marks: list[str] = []

    async def _track_mark(*_a: object, **_k: object) -> None:
        marks.append("mark")

    monkeypatch.setattr(wh, "_mark_factura_as_paid_and_audit", _track_mark)
    monkeypatch.setattr(
        reconciliation_service.ReconciliationEngine,
        "poll_pending_queue",
        AsyncMock(return_value={"processed": 0, "completed": 0, "failed": 0}),
    )

    db = _FakeSupabase()
    body = b"{}"
    payload = {
        "events": [
            {
                "id": "EVDUP99",
                "resource_type": "payments",
                "action": "confirmed",
                "links": {},
                "metadata": {},
            },
            {
                "id": "EVDUP99",
                "resource_type": "payments",
                "action": "confirmed",
                "links": {},
                "metadata": {},
            },
        ],
    }
    await wh._process_gocardless_webhook(db=db, payload=payload, body=body)  # type: ignore[arg-type]
    assert len(marks) == 1
