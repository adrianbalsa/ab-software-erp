from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_stripe_webhook_alias_route_exists(client, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _stub_handle_webhook(*, payload: bytes, sig_header: str | None, db) -> dict[str, object]:
        _ = (payload, sig_header, db)
        return {"received": True}

    monkeypatch.setattr("app.services.stripe_service.handle_webhook", _stub_handle_webhook)
    res = await client.post(
        "/api/v1/payments/stripe/webhook",
        headers={"Stripe-Signature": "t=1,v1=test"},
        content=b"{}",
    )
    assert res.status_code == 200
    assert res.json().get("received") is True
