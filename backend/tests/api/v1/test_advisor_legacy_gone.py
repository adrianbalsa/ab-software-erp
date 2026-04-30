"""Rutas legacy ``/ai/chat`` y ``/ai/consult`` devuelven 410 con pista al canónico ``/api/v1/advisor/ask``."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_legacy_ai_chat_returns_410_with_canonical_hint(client) -> None:
    res = await client.post("/ai/chat", json={"message": "hola", "history": []})
    assert res.status_code == 410
    body = res.json()
    assert body.get("detail", {}).get("canonical_path") == "/api/v1/advisor/ask"


@pytest.mark.asyncio
async def test_legacy_ai_consult_returns_410_with_canonical_hint(client) -> None:
    res = await client.post("/ai/consult", json={"query": "diagnóstico"})
    assert res.status_code == 410
    body = res.json()
    assert body.get("detail", {}).get("canonical_path") == "/api/v1/advisor/ask"
