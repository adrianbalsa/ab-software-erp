"""Las respuestas de error HTTP incluyen ``request_id`` para soporte."""

from __future__ import annotations


async def test_request_validation_error_includes_request_id(client) -> None:
    res = await client.post("/auth/login", json={"unexpected": "body"})
    assert res.status_code == 422
    body = res.json()
    assert isinstance(body.get("request_id"), str)
    assert len(body["request_id"]) >= 8


async def test_http_exception_includes_request_id(client) -> None:
    res = await client.get("/api/v1/gastos/importar-combustible/jobs/00000000-0000-0000-0000-000000000099")
    assert res.status_code in (401, 403, 404)
    body = res.json()
    assert isinstance(body.get("request_id"), str)
