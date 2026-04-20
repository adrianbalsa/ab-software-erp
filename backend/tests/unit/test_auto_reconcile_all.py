from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.reconciliation_service import ReconciliationService


@pytest.mark.asyncio
async def test_auto_reconcile_all_paginates_empresas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_RECONCILE_EMPRESA_PAGE_SIZE", "2")
    monkeypatch.setenv("AUTO_RECONCILE_SKIP_INACTIVE_TENANTS", "false")

    reconcile_hits: list[str] = []

    async def fake_reconcile(eid: str) -> tuple[int, list[dict[str, object]]]:
        reconcile_hits.append(eid)
        return 0, []

    db = MagicMock()
    svc = ReconciliationService(db=db, logis_advisor=None)
    monkeypatch.setattr(svc, "auto_reconcile_invoices", fake_reconcile)

    async def emp_execute(_q: object) -> object:
        if not hasattr(emp_execute, "n"):
            emp_execute.n = 0  # type: ignore[attr-defined]
        n = emp_execute.n  # type: ignore[attr-defined]
        emp_execute.n = n + 1  # type: ignore[attr-defined]
        if n == 0:
            return SimpleNamespace(
                data=[
                    {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1"},
                    {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2"},
                ]
            )
        if n == 1:
            return SimpleNamespace(data=[{"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3"}])
        return SimpleNamespace(data=[])

    db.execute = AsyncMock(side_effect=emp_execute)

    def table_side_effect(name: str) -> MagicMock:
        t = MagicMock()
        if name == "empresas":

            def range_(lo: int, hi: int) -> object:
                return SimpleNamespace(_range=(lo, hi))

            sel = t.select.return_value
            ord_ = sel.order.return_value
            ord_.is_.return_value = ord_
            ord_.range.side_effect = range_
            return t
        return MagicMock()

    db.table.side_effect = table_side_effect

    total, per = await svc.auto_reconcile_all()
    assert total == 0
    assert set(per.keys()) == {
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1",
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2",
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3",
    }
    assert reconcile_hits == [
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1",
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2",
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3",
    ]
    # Última página parcial (< page_size) no dispara un tercer SELECT vacío.
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_auto_reconcile_all_single_empresa(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock()
    svc = ReconciliationService(db=db, logis_advisor=None)
    spy = AsyncMock(return_value=(2, [{"factura_id": 1, "transaction_id": "t1"}]))
    monkeypatch.setattr(svc, "auto_reconcile_invoices", spy)
    total, per = await svc.auto_reconcile_all(empresa_id="  bb111111-1111-1111-1111-111111111111  ")
    assert total == 2
    assert per == {"bb111111-1111-1111-1111-111111111111": 2}
    spy.assert_awaited_once_with("bb111111-1111-1111-1111-111111111111")
