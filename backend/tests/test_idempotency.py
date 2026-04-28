from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.middleware.idempotency_middleware import IdempotencyMiddleware


@dataclass
class _StoredItem:
    value: str
    expire_at: float | None


class _FakeRedis:
    def __init__(self) -> None:
        self._now = 1_000.0
        self._store: dict[str, _StoredItem] = {}

    def advance(self, seconds: float) -> None:
        self._now += seconds

    async def get(self, key: str) -> str | None:
        item = self._store.get(key)
        if item is None:
            return None
        if item.expire_at is not None and self._now >= item.expire_at:
            self._store.pop(key, None)
            return None
        return item.value

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        expire_at = self._now + float(ex) if ex is not None else None
        self._store[key] = _StoredItem(value=value, expire_at=expire_at)
        return True


def _build_app(counter: dict[str, int]) -> Starlette:
    async def mutate(request: Request) -> JSONResponse:
        payload = await request.json()
        counter["value"] += 1
        return JSONResponse(
            {
                "counter": counter["value"],
                "payload": payload,
            },
            status_code=201,
        )

    async def read(_request: Request) -> JSONResponse:
        counter["value"] += 1
        return JSONResponse({"counter": counter["value"]}, status_code=200)

    app = Starlette(
        routes=[
            Route("/api/v1/facturas/", mutate, methods=["POST"]),
            Route("/api/v1/facturas/", read, methods=["GET", "HEAD", "OPTIONS"]),
        ]
    )
    app.add_middleware(IdempotencyMiddleware)
    return app


@pytest.mark.asyncio
async def test_idempotency_replay_successful(mock_user_empresa_a: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = _FakeRedis()
    counter = {"value": 0}
    app = _build_app(counter)
    async def _fake_get_redis(_self) -> _FakeRedis:
        return fake_redis

    monkeypatch.setattr(IdempotencyMiddleware, "_redis", _fake_get_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": f"Bearer {mock_user_empresa_a['jwt']}",
            "Idempotency-Key": "unique-key-001",
            "Content-Type": "application/json",
        }
        payload = {"num_factura": "F-2026-001", "total": 120.55}
        first = await client.post("/api/v1/facturas/", headers=headers, json=payload)
        fake_redis.advance(1.0)
        second = await client.post("/api/v1/facturas/", headers=headers, json=payload)

    assert first.status_code == second.status_code == 201
    assert first.text == second.text
    assert second.headers.get("X-Idempotency-Replayed") == "true"
    assert counter["value"] == 1


@pytest.mark.asyncio
async def test_idempotency_anti_collision_tenant_isolation(
    mock_user_empresa_a: dict[str, object],
    mock_user_empresa_b: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = _FakeRedis()
    counter = {"value": 0}
    app = _build_app(counter)
    async def _fake_get_redis(_self) -> _FakeRedis:
        return fake_redis

    monkeypatch.setattr(IdempotencyMiddleware, "_redis", _fake_get_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        common = {"Idempotency-Key": "clave-123", "Content-Type": "application/json"}
        a_headers = {"Authorization": f"Bearer {mock_user_empresa_a['jwt']}", **common}
        b_headers = {"Authorization": f"Bearer {mock_user_empresa_b['jwt']}", **common}

        a_resp = await client.post("/api/v1/facturas/", headers=a_headers, json={"tenant": "A", "value": 10})
        b_resp = await client.post("/api/v1/facturas/", headers=b_headers, json={"tenant": "B", "value": 99})

    assert a_resp.status_code == 201
    assert b_resp.status_code == 201
    assert b_resp.headers.get("X-Idempotency-Replayed") is None
    assert json.loads(a_resp.text)["payload"]["tenant"] == "A"
    assert json.loads(b_resp.text)["payload"]["tenant"] == "B"
    assert counter["value"] == 2


@pytest.mark.asyncio
async def test_idempotency_expiration_allows_new_processing(
    mock_user_empresa_a: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = _FakeRedis()
    counter = {"value": 0}
    app = _build_app(counter)
    async def _fake_get_redis(_self) -> _FakeRedis:
        return fake_redis

    monkeypatch.setattr(IdempotencyMiddleware, "_redis", _fake_get_redis)
    monkeypatch.setattr(IdempotencyMiddleware, "TTL_SECONDS", 2)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": f"Bearer {mock_user_empresa_a['jwt']}",
            "Idempotency-Key": "ttl-key",
            "Content-Type": "application/json",
        }
        first = await client.post("/api/v1/facturas/", headers=headers, json={"amount": 10})
        fake_redis.advance(3.0)
        second = await client.post("/api/v1/facturas/", headers=headers, json={"amount": 10})

    assert first.status_code == second.status_code == 201
    assert second.headers.get("X-Idempotency-Replayed") is None
    assert json.loads(first.text)["counter"] == 1
    assert json.loads(second.text)["counter"] == 2
    assert counter["value"] == 2


@pytest.mark.asyncio
async def test_idempotency_ignores_get_head_options(
    mock_user_empresa_a: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = _FakeRedis()
    counter = {"value": 0}
    app = _build_app(counter)
    async def _fake_get_redis(_self) -> _FakeRedis:
        return fake_redis

    monkeypatch.setattr(IdempotencyMiddleware, "_redis", _fake_get_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": f"Bearer {mock_user_empresa_a['jwt']}",
            "Idempotency-Key": "read-key",
        }
        get_1 = await client.get("/api/v1/facturas/", headers=headers)
        get_2 = await client.get("/api/v1/facturas/", headers=headers)
        opt = await client.options("/api/v1/facturas/", headers=headers)

    assert get_1.status_code == 200
    assert get_2.status_code == 200
    assert opt.status_code == 200
    assert get_2.headers.get("X-Idempotency-Replayed") is None
    assert counter["value"] == 3
