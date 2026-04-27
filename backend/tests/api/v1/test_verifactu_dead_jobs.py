from __future__ import annotations

from uuid import UUID

import pytest

from app.api import deps
from app.models.enums import UserRole
from app.schemas.user import UserOut
from tests.conftest import _FakeQuery, _resolve_seed_empresa_id


def _user_rbac(rbac: str) -> UserOut:
    r = (rbac or "").strip().lower()
    if r == "driver":
        op = UserRole.TRANSPORTISTA
    elif r == "owner":
        op = UserRole.ADMIN
    elif r == "traffic_manager":
        op = UserRole.GESTOR
    else:
        op = UserRole.GESTOR
    return UserOut(
        username="dead-jobs-test@ab-logistics.test",
        empresa_id=_resolve_seed_empresa_id(),
        role=op,
        rol="user",
        rbac_role=r,
        usuario_id=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
    )


class _DeadJobsChain:
    def __init__(self, db: "_DeadJobsDb") -> None:
        self._db = db
        self._empresa_id: str | None = None
        self._status: str | None = None
        self._range: tuple[int, int] | None = None

    def select(self, *_args: object) -> "_DeadJobsChain":
        return self

    def eq(self, col: str, val: object) -> "_DeadJobsChain":
        if col == "empresa_id":
            self._empresa_id = str(val)
        elif col == "status":
            self._status = str(val)
        return self

    def order(self, *_a: object, **_k: object) -> "_DeadJobsChain":
        return self

    def range(self, start: int, end: int) -> "_DeadJobsChain":
        self._range = (start, end)
        return self

    def execute(self) -> object:
        rows = [dict(r) for r in self._db.ROWS if str(r["empresa_id"]) == str(self._empresa_id)]
        if self._status is not None:
            rows = [x for x in rows if x["status"] == self._status]
        if self._range is not None:
            a, b = self._range
            rows = rows[a : b + 1]

        class _R:
            data = rows

        return _R()


def _sample_rows_for_client_tenant() -> list[dict]:
    eid = str(_resolve_seed_empresa_id())
    return [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "empresa_id": eid,
            "factura_id": 42,
            "job_name": "submit_to_aeat",
            "job_try": 5,
            "max_tries": 5,
            "error_type": "Timeout",
            "error_message": "upstream",
            "status": "open",
            "resolved_at": None,
            "created_at": "2026-04-01T10:00:00+00:00",
            "updated_at": "2026-04-01T10:00:00+00:00",
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "empresa_id": eid,
            "factura_id": 99,
            "job_name": "submit_to_aeat",
            "job_try": 3,
            "max_tries": 3,
            "error_type": None,
            "error_message": None,
            "status": "resolved",
            "resolved_at": "2026-04-02T10:00:00+00:00",
            "created_at": "2026-04-02T09:00:00+00:00",
            "updated_at": "2026-04-02T10:00:00+00:00",
        },
    ]


class _DeadJobsDb:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.ROWS = list(rows) if rows is not None else _sample_rows_for_client_tenant()

    def table(self, name: str) -> _DeadJobsChain | _FakeQuery:
        if name == "verifactu_dead_jobs":
            return _DeadJobsChain(self)
        return _FakeQuery()

    async def execute(self, query: object) -> object:
        return query.execute()


@pytest.mark.asyncio
async def test_dead_jobs_default_returns_empty_list(client) -> None:
    res = await client.get("/api/v1/verifactu/dead-jobs")
    assert res.status_code == 200
    body = res.json()
    assert body["items"] == []
    assert body["limit"] == 50
    assert body["offset"] == 0


@pytest.mark.asyncio
async def test_dead_jobs_driver_gets_403(client) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_current_user] = lambda: _user_rbac("driver")
    app.dependency_overrides[deps.bind_write_context] = lambda: _user_rbac("driver")
    try:
        res = await client.get("/api/v1/verifactu/dead-jobs")
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dead_jobs_returns_rows_for_owner(client) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_db] = lambda: _DeadJobsDb()
    try:
        res = await client.get("/api/v1/verifactu/dead-jobs?limit=10&offset=0")
        assert res.status_code == 200
        body = res.json()
        assert len(body["items"]) == 2
        ids = {it["id"] for it in body["items"]}
        assert ids == {
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        }
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dead_jobs_status_filter(client) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_db] = lambda: _DeadJobsDb()
    try:
        res = await client.get("/api/v1/verifactu/dead-jobs?status=open")
        assert res.status_code == 200
        body = res.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["status"] == "open"
        assert body["items"][0]["factura_id"] == 42
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dead_jobs_invalid_status(client) -> None:
    res = await client.get("/api/v1/verifactu/dead-jobs?status=nope")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_dead_jobs_truncates_long_error_message(client) -> None:
    long_msg = "x" * 5000
    row = {
        "id": "33333333-3333-3333-3333-333333333333",
        "empresa_id": str(_resolve_seed_empresa_id()),
        "factura_id": 7,
        "job_name": "submit_to_aeat",
        "job_try": 2,
        "max_tries": 2,
        "error_type": "Err",
        "error_message": long_msg,
        "status": "open",
        "resolved_at": None,
        "created_at": "2026-04-03T10:00:00+00:00",
        "updated_at": "2026-04-03T10:00:00+00:00",
    }

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_db] = lambda: _DeadJobsDb(rows=[row])
    try:
        res = await client.get("/api/v1/verifactu/dead-jobs")
        assert res.status_code == 200
        msg = res.json()["items"][0]["error_message"]
        assert msg is not None
        assert len(msg) == 4001
        assert msg.endswith("…")
    finally:
        app.dependency_overrides.clear()
