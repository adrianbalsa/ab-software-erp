from __future__ import annotations

import asyncio

import pytest

from app.services.usage_service import UsageService


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, int] = {}

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def set(self, key: str, value: int, nx: bool | None = None, ex: int | None = None) -> bool:
        _ = ex
        if nx and key in self._store:
            return False
        self._store[key] = int(value)
        return True

    async def get(self, key: str) -> str | None:
        value = self._store.get(key)
        if value is None:
            return None
        return str(value)

    async def eval(self, _script: str, _numkeys: int, credits_key: str, pending_key: str, amount: int):
        current = int(self._store.get(credits_key, 0))
        if current < int(amount):
            return [0, current]
        remaining = current - int(amount)
        self._store[credits_key] = remaining
        self._store[pending_key] = int(self._store.get(pending_key, 0)) + int(amount)
        return [1, remaining]


@pytest.mark.asyncio
async def test_low_credit_consumption_triggers_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = _FakeRedis()
    sent_alerts: list[dict[str, object]] = []
    scheduled_tasks: list[asyncio.Task[None]] = []

    async def _fake_get_redis(cls):
        _ = cls
        return fake_redis

    async def _fake_send_alert(title: str, message: str, level: str = "INFO", context: dict | None = None) -> None:
        sent_alerts.append(
            {
                "title": title,
                "message": message,
                "level": level,
                "context": context or {},
            }
        )

    def _fake_create_task(coro):
        task = asyncio.get_running_loop().create_task(coro)
        scheduled_tasks.append(task)
        return task

    monkeypatch.setattr(UsageService, "_get_redis", classmethod(_fake_get_redis))
    monkeypatch.setattr("app.services.usage_service.send_alert", _fake_send_alert)
    monkeypatch.setattr("app.services.usage_service.asyncio.create_task", _fake_create_task)

    service = UsageService(db=None)
    result = await service.consume_credits(
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        amount=901,
        plan="starter",
    )

    if scheduled_tasks:
        await asyncio.gather(*scheduled_tasks)

    assert result.allowed is True
    assert result.remaining_credits == 99
    assert len(sent_alerts) == 1
    assert sent_alerts[0]["level"] == "WARNING"
    assert sent_alerts[0]["context"]["tenant_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
