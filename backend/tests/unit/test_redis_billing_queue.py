from __future__ import annotations

import importlib

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError


class _FakeResult:
    def __init__(self, data: list[dict[str, object]] | None = None) -> None:
        self.data = data or []


class _FakeQuery:
    def __init__(self, table: str, op: str | None = None, payload: object | None = None) -> None:
        self.table = table
        self.op = op
        self.payload = payload
        self.filters: list[tuple[str, object]] = []

    def select(self, _columns: str = "*", **_kwargs: object) -> "_FakeQuery":
        self.op = "select"
        return self

    def insert(self, payload: object) -> "_FakeQuery":
        self.op = "insert"
        self.payload = payload
        return self

    def eq(self, column: str, value: object) -> "_FakeQuery":
        self.filters.append((column, value))
        return self

    def limit(self, _count: int) -> "_FakeQuery":
        return self


class _FakeDb:
    def __init__(self, *, existing_dead_job: bool = False) -> None:
        self.existing_dead_job = existing_dead_job
        self.inserts: list[tuple[str, object]] = []

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(name)

    async def execute(self, query: _FakeQuery) -> _FakeResult:
        if query.table == "verifactu_dead_jobs" and query.op == "select":
            return _FakeResult([{"id": "existing"}] if self.existing_dead_job else [])
        if query.table == "verifactu_dead_jobs" and query.op == "insert":
            self.inserts.append((query.table, query.payload))
        return _FakeResult([])


def test_redis_settings_support_sentinel(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.core.redis_config import redis_settings_from_env

    monkeypatch.setenv("REDIS_URL", "rediss://user:pass@redis-primary:6379/2")
    monkeypatch.setenv("REDIS_SENTINEL_HOSTS", "sentinel-a:26379,sentinel-b:26380")
    monkeypatch.setenv("REDIS_SENTINEL_MASTER", "abl-master")
    monkeypatch.setenv("REDIS_MAX_CONNECTIONS", "42")
    get_settings.cache_clear()

    settings = redis_settings_from_env(purpose="test")

    assert settings.sentinel is True
    assert settings.host == [("sentinel-a", 26379), ("sentinel-b", 26380)]
    assert settings.sentinel_master == "abl-master"
    assert settings.username == "user"
    assert settings.password == "pass"
    assert settings.database == 2
    assert settings.ssl is True
    assert settings.retry_on_timeout is True
    assert settings.max_connections == 42


def test_worker_retry_helpers(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()

    worker = importlib.import_module("app.worker")

    assert worker._retry_defer_seconds({"job_try": 1}) == 10
    assert worker._retry_defer_seconds({"job_try": 3}) == 40
    assert worker._retry_defer_seconds({"job_try": 99}) == 300
    assert worker._can_retry_job({"job_try": 5}) is True
    assert worker._can_retry_job({"job_try": 6}) is False
    assert worker._is_retryable_exception(RedisConnectionError("down")) is True
    assert worker._is_retryable_result(
        {
            "aeat_sif_estado": "pendiente_envio",
            "aeat_sif_codigo": "AEAT_TIMEOUT",
        }
    )
    assert not worker._is_retryable_result(
        {
            "aeat_sif_estado": "rechazado",
            "aeat_sif_codigo": "VALIDATION",
        }
    )


def test_queue_growth_alert_state_triggers_after_threshold() -> None:
    from app.core.health_checks import _queue_growth_alert_state

    payload = _queue_growth_alert_state(
        queue_depth=42,
        previous_depth=30,
        previous_growth_started_at=1_000.0,
        now_ts=1_901.0,
        threshold_minutes=15,
        min_depth=10,
    )

    assert payload["queue_growth_alert"] is True
    assert payload["queue_growth_detail"] == "queue_depth_growing_sustained"
    assert payload["queue_growth_duration_seconds"] == 901


def test_queue_growth_alert_state_resets_when_depth_stops_growing() -> None:
    from app.core.health_checks import _queue_growth_alert_state

    payload = _queue_growth_alert_state(
        queue_depth=42,
        previous_depth=42,
        previous_growth_started_at=1_000.0,
        now_ts=2_000.0,
        threshold_minutes=15,
        min_depth=10,
    )

    assert payload["queue_growth_alert"] is False
    assert payload["queue_growth_detail"] == "queue_depth_stable_or_below_threshold"
    assert payload["queue_growth_started_at"] is None
    assert payload["queue_growth_duration_seconds"] == 0


@pytest.mark.asyncio
async def test_queue_growth_payload_persists_recovery_state(monkeypatch) -> None:
    from app.core import health_checks

    class FakeRedis:
        def __init__(self) -> None:
            self.data = {
                "last_depth": b"12",
                "growth_started_at": b"1000",
            }
            self.expire_ttl: int | None = None

        async def hgetall(self, _key: str) -> dict[str, bytes]:
            return dict(self.data)

        async def hset(self, _key: str, *, mapping: dict[str, object]) -> None:
            self.data = {k: str(v).encode("utf-8") for k, v in mapping.items()}

        async def expire(self, _key: str, ttl: int) -> None:
            self.expire_ttl = ttl

    fake = FakeRedis()
    monkeypatch.setenv("REDIS_QUEUE_GROWTH_ALERT_MINUTES", "15")
    monkeypatch.setenv("REDIS_QUEUE_GROWTH_MIN_DEPTH", "10")
    monkeypatch.setattr(health_checks.time, "time", lambda: 2_000.0)

    payload = await health_checks._queue_growth_alert_payload(
        fake,
        queue_name="arq:queue",
        queue_depth=8,
    )

    assert payload["queue_growth_alert"] is False
    assert payload["queue_growth_detail"] == "queue_depth_stable_or_below_threshold"
    assert fake.data["last_depth"] == b"8"
    assert fake.data["growth_started_at"] == b""
    assert fake.expire_ttl == 3600


@pytest.mark.asyncio
async def test_record_verifactu_dead_job_inserts_open_row(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()
    worker = importlib.import_module("app.worker")
    db = _FakeDb()

    await worker._record_verifactu_dead_job(
        db,
        factura_id=123,
        empresa_id="00000000-0000-0000-0000-000000000001",
        ctx={"job_try": 6},
        result={
            "aeat_sif_estado": "pendiente_envio",
            "aeat_sif_codigo": "AEAT_TIMEOUT",
            "aeat_sif_descripcion": "timeout AEAT",
        },
        exc=None,
    )

    assert len(db.inserts) == 1
    table, payload = db.inserts[0]
    assert table == "verifactu_dead_jobs"
    assert isinstance(payload, dict)
    assert payload["factura_id"] == 123
    assert payload["job_name"] == "submit_to_aeat"
    assert payload["job_try"] == 6
    assert payload["max_tries"] == 6
    assert payload["status"] == "open"
    assert payload["error_type"] == "RetryableResultExhausted"
    assert payload["error_message"] == "timeout AEAT"


@pytest.mark.asyncio
async def test_record_verifactu_dead_job_is_idempotent(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()
    worker = importlib.import_module("app.worker")
    db = _FakeDb(existing_dead_job=True)

    await worker._record_verifactu_dead_job(
        db,
        factura_id=123,
        empresa_id="00000000-0000-0000-0000-000000000001",
        ctx={"job_try": 6},
        result=None,
        exc=RuntimeError("exhausted"),
    )

    assert db.inserts == []


@pytest.mark.asyncio
async def test_submit_to_aeat_records_dead_job_when_retries_exhausted(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()
    worker = importlib.import_module("app.worker")
    db = _FakeDb()

    async def _noop_acquire(_ctx: dict[str, object]) -> None:
        return None

    async def _fake_sender(_factura_id: str) -> dict[str, object]:
        return {
            "aeat_sif_estado": "pendiente_envio",
            "aeat_sif_codigo": "AEAT_TIMEOUT",
            "aeat_sif_descripcion": "timeout AEAT",
        }

    async def _fake_get_supabase(**_kwargs: object) -> _FakeDb:
        return db

    monkeypatch.setattr(worker, "_acquire_aeat_egress_slot", _noop_acquire)
    monkeypatch.setattr(worker, "_is_mock_mode_enabled", lambda: False)
    monkeypatch.setattr(worker, "enviar_factura_aeat", _fake_sender)
    monkeypatch.setattr(worker, "get_supabase", _fake_get_supabase)

    with pytest.raises(RuntimeError, match="AEAT retry exhausted"):
        await worker.submit_to_aeat(
            {"job_try": 6},
            factura_id=123,
            empresa_id="00000000-0000-0000-0000-000000000001",
        )

    assert len(db.inserts) == 1
    table, payload = db.inserts[0]
    assert table == "verifactu_dead_jobs"
    assert isinstance(payload, dict)
    assert payload["factura_id"] == 123
    assert payload["status"] == "open"
