from __future__ import annotations

import pytest

from app.core.plans import CostMeter
from app.services import usage_quota_service as usage_mod
from app.services.usage_quota_service import UsageQuotaExceeded, UsageQuotaService, estimate_ai_tokens


class _Result:
    def __init__(self, data: list[dict[str, object]]) -> None:
        self.data = data


class _Query:
    def __init__(self, db: "_Db") -> None:
        self._db = db
        self.filters: dict[str, object] = {}

    def select(self, *_a: object, **_k: object) -> "_Query":
        return self

    def eq(self, key: str, value: object) -> "_Query":
        self.filters[key] = value
        return self


class _Db:
    def __init__(
        self,
        *,
        rpc_rows: list[dict[str, object]] | None = None,
        memory_mode: bool = False,
    ) -> None:
        self.rpc_rows = rpc_rows or []
        self.rpc_params: dict[str, object] | None = None
        self.memory_mode = memory_mode
        self.usage: dict[tuple[str, str, str], dict[str, object]] = {}

    async def rpc(self, _fn: str, params: dict[str, object]) -> _Result:
        self.rpc_params = params
        if self.memory_mode:
            eid = str(params["p_empresa_id"])
            period = str(params["p_period_yyyymm"])
            meter = str(params["p_meter"])
            units = int(params["p_units"])
            limit = int(params["p_limit_units"])
            key = (eid, period, meter)
            row = self.usage.get(
                key,
                {"empresa_id": eid, "period_yyyymm": period, "meter": meter, "used_units": 0, "limit_units": limit},
            )
            attempted = int(row["used_units"]) + units
            if attempted > limit:
                return _Result([{**row, "limit_units": limit, "allowed": False}])
            row = {**row, "used_units": attempted, "limit_units": limit}
            self.usage[key] = row
            return _Result([{**row, "allowed": True}])
        return _Result(self.rpc_rows)

    def table(self, _name: str) -> _Query:
        return _Query(self)

    async def execute(self, query: object) -> _Result:
        if isinstance(query, _Query) and self.memory_mode:
            rows = [
                row
                for (eid, period, _meter), row in self.usage.items()
                if eid == str(query.filters.get("empresa_id"))
                and period == str(query.filters.get("period_yyyymm"))
            ]
            return _Result(rows)
        return _Result([{"meter": CostMeter.OCR.value, "used_units": 3, "limit_units": 20}])


@pytest.mark.asyncio
async def test_consume_records_quota_with_plan_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_plan(_db: object, *, empresa_id: str) -> str:
        assert empresa_id == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        return "starter"

    monkeypatch.setattr(usage_mod, "fetch_empresa_plan", fake_fetch_plan)
    db = _Db(
        rpc_rows=[
            {
                "allowed": True,
                "used_units": 4,
                "limit_units": 20,
            }
        ]
    )

    out = await UsageQuotaService(db).consume(  # type: ignore[arg-type]
        empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        meter=CostMeter.OCR,
    )

    assert out.remaining_units == 16
    assert db.rpc_params is not None
    assert db.rpc_params["p_meter"] == "ocr_pages_month"
    assert db.rpc_params["p_limit_units"] == 20


@pytest.mark.asyncio
async def test_consume_raises_payment_required_when_cap_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_plan(_db: object, *, empresa_id: str) -> str:
        return "starter"

    monkeypatch.setattr(usage_mod, "fetch_empresa_plan", fake_fetch_plan)
    db = _Db(rpc_rows=[{"allowed": False, "used_units": 20, "limit_units": 20}])

    with pytest.raises(UsageQuotaExceeded) as exc:
        await UsageQuotaService(db).consume(  # type: ignore[arg-type]
            empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            meter="ocr",
        )

    assert exc.value.status_code == 402
    assert exc.value.detail["code"] == "monthly_cost_quota_exceeded"


@pytest.mark.asyncio
async def test_current_usage_includes_zero_rows_for_unused_meters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_plan(_db: object, *, empresa_id: str) -> str:
        return "starter"

    monkeypatch.setattr(usage_mod, "fetch_empresa_plan", fake_fetch_plan)

    out = await UsageQuotaService(_Db()).current_usage(  # type: ignore[arg-type]
        empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    )

    by_meter = {m.meter: m for m in out.meters}
    assert by_meter["ocr_pages_month"].used_units == 3
    assert by_meter["maps_calls_month"].used_units == 0
    assert by_meter["ai_tokens_month"].remaining_units == 100_000


@pytest.mark.asyncio
async def test_hard_cap_allows_exact_limit_and_blocks_overage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_plan(_db: object, *, empresa_id: str) -> str:
        return "starter"

    monkeypatch.setattr(usage_mod, "fetch_empresa_plan", fake_fetch_plan)
    monkeypatch.setattr(usage_mod, "current_usage_period", lambda: "2026-04")
    db = _Db(memory_mode=True)
    service = UsageQuotaService(db)  # type: ignore[arg-type]

    first = await service.consume(
        empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        meter=CostMeter.MAPS,
        units=100,
    )

    assert first.used_units == 100
    assert first.remaining_units == 0
    with pytest.raises(UsageQuotaExceeded):
        await service.consume(
            empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            meter=CostMeter.MAPS,
            units=1,
        )


@pytest.mark.asyncio
async def test_monthly_window_resets_by_period(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_plan(_db: object, *, empresa_id: str) -> str:
        return "starter"

    period = "2026-04"
    monkeypatch.setattr(usage_mod, "fetch_empresa_plan", fake_fetch_plan)
    monkeypatch.setattr(usage_mod, "current_usage_period", lambda: period)
    db = _Db(memory_mode=True)
    service = UsageQuotaService(db)  # type: ignore[arg-type]

    april = await service.consume(
        empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        meter=CostMeter.OCR,
        units=20,
    )
    period = "2026-05"
    may = await service.consume(
        empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        meter=CostMeter.OCR,
        units=1,
    )

    assert april.used_units == 20
    assert may.period_yyyymm == "2026-05"
    assert may.used_units == 1
    assert may.remaining_units == 19


@pytest.mark.asyncio
async def test_usage_is_isolated_between_tenants(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_plan(_db: object, *, empresa_id: str) -> str:
        return "starter"

    monkeypatch.setattr(usage_mod, "fetch_empresa_plan", fake_fetch_plan)
    monkeypatch.setattr(usage_mod, "current_usage_period", lambda: "2026-04")
    db = _Db(memory_mode=True)
    service = UsageQuotaService(db)  # type: ignore[arg-type]

    tenant_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    tenant_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    await service.consume(empresa_id=tenant_a, meter=CostMeter.OCR, units=20)
    tenant_b_usage = await service.consume(empresa_id=tenant_b, meter=CostMeter.OCR, units=1)

    assert tenant_b_usage.used_units == 1
    assert tenant_b_usage.remaining_units == 19
    with pytest.raises(UsageQuotaExceeded):
        await service.consume(empresa_id=tenant_a, meter=CostMeter.OCR, units=1)


def test_estimate_ai_tokens_has_minimum_and_scales_with_text() -> None:
    assert estimate_ai_tokens("hola", minimum=500, output_reserve=0) == 500
    assert estimate_ai_tokens("x" * 8_000, minimum=500, output_reserve=1_000) == 3_000
