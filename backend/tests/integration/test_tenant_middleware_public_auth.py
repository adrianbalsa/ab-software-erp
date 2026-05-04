"""Rutas de auth v1 anónimas y preflight CORS no deben bloquearse por TenantRBACContextMiddleware."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_options_forgot_password_not_blocked_by_tenant_middleware(client) -> None:
    res = await client.options(
        "/api/v1/auth/forgot-password",
        headers={
            "Origin": "https://ablogistics-os.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert res.status_code != 403
    if res.status_code == 403:
        detail = str((res.json() or {}).get("detail", ""))
        assert "tenant context" not in detail.lower()


@pytest.mark.asyncio
async def test_post_forgot_password_not_blocked_by_tenant_middleware(client) -> None:
    """POST sin Bearer: antes devolvía 403 del middleware; debe llegar al handler (p. ej. 200/422/502)."""
    res = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@example.com"},
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code != 403
    if res.status_code == 403:
        detail = str((res.json() or {}).get("detail", ""))
        assert "tenant context" not in detail.lower()
