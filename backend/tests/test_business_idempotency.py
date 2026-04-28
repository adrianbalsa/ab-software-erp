from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.middleware.idempotency_middleware import IdempotencyMiddleware


@dataclass
class _StoredItem:
    value: str
    expire_at: float | None


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, _StoredItem] = {}

    async def get(self, key: str) -> str | None:
        item = self._store.get(key)
        if item is None:
            return None
        return item.value

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._store[key] = _StoredItem(value=value, expire_at=None if ex is None else float(ex))
        return True


def _business_app(db: list[dict[str, object]]) -> FastAPI:
    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)

    @app.post("/api/v1/facturas/", status_code=201)
    async def create_factura(request: Request) -> JSONResponse:
        payload = await request.json()
        factura_id = len(db) + 1
        row = {"id": factura_id, **payload}
        db.append(row)
        return JSONResponse(status_code=201, content=row)

    return app


@pytest.mark.asyncio
async def test_business_factura_creation_is_idempotent(
    mock_user_empresa_a: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = _FakeRedis()
    db_rows: list[dict[str, object]] = []
    app = _business_app(db_rows)

    async def _fake_get_redis(_self) -> _FakeRedis:
        return fake_redis

    monkeypatch.setattr(IdempotencyMiddleware, "_redis", _fake_get_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": f"Bearer {mock_user_empresa_a['jwt']}",
            "Idempotency-Key": "factura-001",
            "Content-Type": "application/json",
        }
        payload = {"numero_factura": "F-2026-9001", "total_factura": 199.99}
        first = await client.post("/api/v1/facturas/", headers=headers, json=payload)
        second = await client.post("/api/v1/facturas/", headers=headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.headers.get("X-Idempotency-Replayed") == "true"
    assert len(db_rows) == 1
    assert db_rows[0]["numero_factura"] == "F-2026-9001"


@pytest.mark.asyncio
async def test_idempotency_fail_open_when_redis_unavailable(
    mock_user_empresa_a: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_rows: list[dict[str, object]] = []
    app = _business_app(db_rows)

    class _BrokenRedis:
        async def get(self, _key: str) -> str | None:
            raise RuntimeError("redis down")

        async def set(self, _key: str, _value: str, ex: int | None = None) -> bool:
            _ = ex
            raise RuntimeError("redis down")

    async def _fake_get_redis(_self) -> _BrokenRedis:
        return _BrokenRedis()

    monkeypatch.setattr(IdempotencyMiddleware, "_redis", _fake_get_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "Authorization": f"Bearer {mock_user_empresa_a['jwt']}",
            "Idempotency-Key": "factura-redis-down",
            "Content-Type": "application/json",
        }
        payload = {"numero_factura": "F-2026-9002", "total_factura": 10.0}
        first = await client.post("/api/v1/facturas/", headers=headers, json=payload)
        second = await client.post("/api/v1/facturas/", headers=headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    # Sin Redis no hay replay, pero el negocio sigue operativo (fail-open).
    assert second.headers.get("X-Idempotency-Replayed") is None
    assert len(db_rows) == 2
