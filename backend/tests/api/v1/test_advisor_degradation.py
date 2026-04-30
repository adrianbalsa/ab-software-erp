"""Degradación controlada de ``POST /api/v1/advisor/ask`` (sin LLM real)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

sys.modules.setdefault("litellm", MagicMock(name="litellm_test_double"))
sys.modules.setdefault("anthropic", MagicMock(name="anthropic_test_double"))

from app.api import deps
from app.core.plans import CostMeter
from app.services.usage_quota_service import QuotaConsumption
from app.services.usage_service import UsageResult, UsageService


class _ChatPersistenceStub:
    _sid = str(uuid4())

    async def archive_inactive_sessions(self, **_k: object) -> None:
        return None

    async def apply_retention_policy(self, **_k: object) -> None:
        return None

    async def create_session(self, **_k: object) -> dict[str, object]:
        return {"id": self._sid}

    async def get_context_history(self, **_k: object) -> list[dict[str, str]]:
        return []

    async def append_message(self, **_k: object) -> dict[str, object]:
        return {"id": str(uuid4())}


class _AuditStub:
    async def log_sensitive_action(self, **_k: object) -> None:
        return None


class _QuotaStub:
    async def consume(
        self,
        *,
        empresa_id: str,
        meter: CostMeter | str,
        units: int = 1,
        plan_type: str | None = None,
    ) -> QuotaConsumption:
        _ = (self, meter, units, plan_type)
        return QuotaConsumption(
            empresa_id=str(empresa_id),
            plan_type="free",
            period_yyyymm="202604",
            meter=CostMeter.AI,
            used_units=1,
            limit_units=1_000_000,
            remaining_units=999_999,
        )


@pytest.mark.asyncio
async def test_advisor_ask_returns_503_when_llm_not_configured(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.v1.advisor.openai_configured", lambda: False)

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_chat_persistence_service] = lambda: _ChatPersistenceStub()
    app.dependency_overrides[deps.get_audit_logs_service] = lambda: _AuditStub()
    app.dependency_overrides[deps.get_usage_quota_service] = lambda: _QuotaStub()

    async def _noop_credits(
        self: UsageService,
        *,
        tenant_id: str,
        amount: int,
        plan: str = "starter",
    ) -> UsageResult:
        _ = (self, tenant_id, amount, plan)
        return UsageResult(allowed=True, remaining_credits=999)

    monkeypatch.setattr(UsageService, "consume_credits", _noop_credits)

    try:
        res = await client.post(
            "/api/v1/advisor/ask",
            json={"message": "hola", "stream": False},
        )
        assert res.status_code == 503
        assert "LogisAdvisor" in res.text or "credenciales" in res.text.lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_advisor_ask_returns_502_when_context_gather_fails(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.v1.advisor.openai_configured", lambda: True)

    async def _boom(**_k: object) -> dict[str, object]:
        raise RuntimeError("db down")

    monkeypatch.setattr("app.api.v1.advisor.gather_advisor_context", _boom)

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_chat_persistence_service] = lambda: _ChatPersistenceStub()
    app.dependency_overrides[deps.get_audit_logs_service] = lambda: _AuditStub()
    app.dependency_overrides[deps.get_usage_quota_service] = lambda: _QuotaStub()

    async def _noop_credits(
        self: UsageService,
        *,
        tenant_id: str,
        amount: int,
        plan: str = "starter",
    ) -> UsageResult:
        _ = (self, tenant_id, amount, plan)
        return UsageResult(allowed=True, remaining_credits=999)

    monkeypatch.setattr(UsageService, "consume_credits", _noop_credits)

    try:
        res = await client.post(
            "/api/v1/advisor/ask",
            json={"message": "hola", "stream": False},
        )
        assert res.status_code == 502
        assert "contexto" in res.text.lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_advisor_ask_json_returns_503_when_provider_raises_runtime_error(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.api.v1.advisor.openai_configured", lambda: True)

    async def _empty_context(**_k: object) -> dict[str, object]:
        return {}

    monkeypatch.setattr("app.api.v1.advisor.gather_advisor_context", _empty_context)

    async def _bad_llm(*_a: object, **_k: object) -> tuple[str, str]:
        raise RuntimeError("provider overloaded")

    monkeypatch.setattr("app.api.v1.advisor.get_advisor_response", _bad_llm)

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_chat_persistence_service] = lambda: _ChatPersistenceStub()
    app.dependency_overrides[deps.get_audit_logs_service] = lambda: _AuditStub()
    app.dependency_overrides[deps.get_usage_quota_service] = lambda: _QuotaStub()

    async def _noop_credits(
        self: UsageService,
        *,
        tenant_id: str,
        amount: int,
        plan: str = "starter",
    ) -> UsageResult:
        _ = (self, tenant_id, amount, plan)
        return UsageResult(allowed=True, remaining_credits=999)

    monkeypatch.setattr(UsageService, "consume_credits", _noop_credits)

    try:
        res = await client.post(
            "/api/v1/advisor/ask",
            json={"message": "hola", "stream": False},
        )
        assert res.status_code == 503
        body = res.json()
        assert "overloaded" in str(body.get("detail", "")).lower()
    finally:
        app.dependency_overrides.clear()
