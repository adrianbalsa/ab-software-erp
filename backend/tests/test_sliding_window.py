from __future__ import annotations

from collections import deque

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

import app.middleware.rate_limit_middleware as rlm
from app.core.config import get_settings
from app.middleware.rate_limit_middleware import TenantRateLimitMiddleware


@pytest.mark.asyncio
async def test_sliding_window_blocks_across_minute_boundary(
    monkeypatch: pytest.MonkeyPatch,
    mock_user_empresa_a: dict[str, object],
) -> None:
    async def ok(_request: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    monkeypatch.setenv("TENANT_RATE_LIMIT_DEFAULT", "100 per minute")
    monkeypatch.setenv(
        "TENANT_RATE_LIMIT_OVERRIDES",
        f"{mock_user_empresa_a['empresa_id']}=2 per minute",
    )
    monkeypatch.delenv("REDIS_URL", raising=False)
    get_settings.cache_clear()
    rlm.TenantRateLimitMiddleware._memory_windows.clear()

    timeline = deque([59.80, 59.90, 60.00])
    monkeypatch.setattr(rlm.time, "time", lambda: timeline[0] if len(timeline) == 1 else timeline.popleft())

    app = Starlette(routes=[Route("/api/v1/facturas", ok, methods=["GET"])])
    app.add_middleware(TenantRateLimitMiddleware)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {mock_user_empresa_a['jwt']}"}
            r1 = await client.get("/api/v1/facturas", headers=headers)
            r2 = await client.get("/api/v1/facturas", headers=headers)
            r3 = await client.get("/api/v1/facturas", headers=headers)
    finally:
        get_settings.cache_clear()
        rlm.TenantRateLimitMiddleware._memory_windows.clear()

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
