"""
E2E (integración API + dominio) — Conciliación bancaria Open Banking / GoCardless → KPIs.

- Simula movimientos persistidos (payload estilo descripción SEPA) con referencia ambigua.
- Orquestador híbrido (``BankingOrchestratorService`` + ``ReconciliationService`` / LLM focalizado).
- ``LogisAdvisor`` (``ai_service.LogisAdvisorService``) lee el mismo ``financial_dashboard`` tras el cobro.
- Auditoría: petición mutante ``POST /api/v1/banking/reconcile`` dispara ``AuditLogMiddleware`` → ``AuditLogsService``.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import deps
from app.core.security import create_access_token
from app.services.ai_service import LogisAdvisorService
from app.services.banking_orchestrator import FUZZY_AI_FLOOR, FUZZY_AUTO_MATCH_THRESHOLD
from app.services.finance_service import FinanceService
from app.services.maps_service import MapsService
from app.services.matching_service import MatchingService
from app.services.secret_manager_service import get_secret_manager, reset_secret_manager
from tests.conftest import EMPRESA_A_ID


class _ExecResult:
    __slots__ = ("data",)

    def __init__(self, data: list[dict[str, Any]] | None = None) -> None:
        self.data = data or []


class _MemQuery:
    def __init__(self, store: "BankingReconciliationMemoryDb", table: str) -> None:
        self._store = store
        self._table = table
        self._op = "select"
        self._cols = "*"
        self._payload: dict[str, Any] | None = None
        self._filters: dict[str, Any] = {}
        self._neq: dict[str, Any] = {}
        self._in_filters: dict[str, list[Any]] = {}
        self._null_if_missing: set[str] = set()
        self._gte: dict[str, Any] = {}
        self._lte: dict[str, Any] = {}
        self._limit: int | None = None
        self._order_desc = False

    def select(self, cols: str = "*") -> _MemQuery:
        self._op = "select"
        self._cols = cols
        return self

    def insert(self, payload: dict[str, Any]) -> _MemQuery:
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload: dict[str, Any]) -> _MemQuery:
        self._op = "update"
        self._payload = payload
        return self

    def eq(self, key: str, value: Any) -> _MemQuery:
        self._filters[key] = value
        return self

    def neq(self, key: str, value: Any) -> _MemQuery:
        self._neq[key] = value
        return self

    def in_(self, key: str, values: list[Any]) -> _MemQuery:
        self._in_filters[key] = list(values)
        return self

    def is_(self, key: str, value: Any) -> _MemQuery:
        if value == "null":
            self._null_if_missing.add(key)
        return self

    def order(self, *_a: object, desc: bool = False, **_k: object) -> _MemQuery:
        self._order_desc = bool(desc)
        return self

    def limit(self, n: int) -> _MemQuery:
        self._limit = int(n)
        return self

    def gte(self, key: str, value: Any) -> _MemQuery:
        self._gte[key] = value
        return self

    def lte(self, key: str, value: Any) -> _MemQuery:
        self._lte[key] = value
        return self

    def execute(self) -> _ExecResult:
        return self._store._execute_table_query(self)


class BankingReconciliationMemoryDb:
    """
    Estado mínimo en memoria para ``MatchingService`` + ``FinanceService`` (vía SupabaseAsync.execute).

    Incluye ``empresas`` (``assert_empresa_billing_active`` / ``get_current_active_user``) y ``profiles``
    (middleware de tenant + ``get_profile_by_subject`` cuando no hay stub de AuthService).
    """

    def __init__(
        self,
        *,
        empresa_id: str,
        cliente_id: str,
        factura_id: int,
        transaction_id: str,
        invoice_number: str,
        bank_description: str,
        invoice_total: Decimal,
        booked_date: str,
        fecha_emision: str,
    ) -> None:
        self.empresa_id = empresa_id
        self.cliente_id = cliente_id
        self.factura_id = factura_id
        self.transaction_id = transaction_id
        self.audit_rpc_calls: list[dict[str, Any]] = []
        self.facturas: list[dict[str, Any]] = [
            {
                "id": factura_id,
                "empresa_id": empresa_id,
                "cliente": cliente_id,
                "numero_factura": invoice_number,
                "num_factura": None,
                "total_factura": float(invoice_total),
                "base_imponible": float((invoice_total / Decimal("1.21")).quantize(Decimal("0.01"))),
                "cuota_iva": float((invoice_total - (invoice_total / Decimal("1.21"))).quantize(Decimal("0.01"))),
                "fecha_emision": fecha_emision,
                "estado_cobro": "emitida",
                "payment_status": "PENDING",
                "pago_id": None,
                "matched_transaction_id": None,
                "fecha_cobro_real": None,
                "total_km_estimados_snapshot": 0.0,
                "is_finalized": True,
                "hash_registro": None,
                "fingerprint": "vf-e2e-banking",
                "tipo_factura": "emitida",
            }
        ]
        self.bank_transactions: list[dict[str, Any]] = [
            {
                "transaction_id": transaction_id,
                "empresa_id": empresa_id,
                "amount": float(invoice_total),
                "booked_date": booked_date,
                "currency": "EUR",
                "description": bank_description,
                "reference": "",
                "reconciled": False,
                "status_reconciled": "pending",
                "internal_status": "imported",
                "remittance_info": None,
                "remittance_information": None,
                "concept": None,
                "concepto": None,
                "end_to_end_id": None,
            }
        ]
        self.clientes: dict[str, dict[str, Any]] = {
            cliente_id: {
                "id": cliente_id,
                "empresa_id": empresa_id,
                "nombre": "Transportes ACME SL",
                "nombre_comercial": "Transportes ACME SL",
            }
        }
        self.gastos: list[dict[str, Any]] = []
        self.gastos_vehiculo: list[dict[str, Any]] = []
        self.portes: list[dict[str, Any]] = []
        # assert_empresa_billing_active → empresas.select(...).eq("id", empresa_id)
        self.empresas: dict[str, dict[str, Any]] = {
            str(empresa_id).strip(): {
                "id": str(empresa_id).strip(),
                "deleted_at": None,
                "stripe_subscription_id": None,
                "plan_type": "enterprise",
            }
        }
        # get_profile_by_subject(subject="admin@qa.local") → profiles por username/email
        self.profiles: list[dict[str, Any]] = [
            {
                "id": str(UUID("99999999-9999-9999-9999-999999999999")),
                "username": "admin@qa.local",
                "email": "admin@qa.local",
                "empresa_id": str(empresa_id).strip(),
                "role": "admin",
                "rol": "admin",
                "cliente_id": None,
                "assigned_vehiculo_id": None,
            }
        ]

    def table(self, name: str) -> _MemQuery:
        return _MemQuery(self, name)

    async def execute(self, query: object) -> _ExecResult:
        if hasattr(query, "execute"):
            return query.execute()
        raise TypeError("query must provide execute()")

    async def rpc(self, fn: str, params: dict[str, Any] | None = None) -> _ExecResult:
        p = params or {}
        if fn == "set_empresa_context":
            return _ExecResult([])
        if fn == "set_rbac_session":
            return _ExecResult([])
        if fn == "audit_logs_insert_api_event":
            self.audit_rpc_calls.append(dict(p))
            return _ExecResult([{"id": str(uuid4())}])
        return _ExecResult([])

    @staticmethod
    def _row_matches(
        row: dict[str, Any],
        *,
        filters: dict[str, Any],
        neq: dict[str, Any],
        in_filters: dict[str, list[Any]],
        null_if_missing: set[str],
        gte: dict[str, Any] | None = None,
        lte: dict[str, Any] | None = None,
    ) -> bool:
        gte = dict(gte or {})
        lte = dict(lte or {})
        for col in null_if_missing:
            if row.get(col) not in (None, ""):
                return False
        for k, low in gte.items():
            rv = row.get(k)
            if rv is None:
                return False
            rs = str(rv).strip()[:10]
            ls = str(low).strip()[:10]
            if len(rs) < 10 or len(ls) < 10:
                return False
            if rs < ls:
                return False
        for k, high in lte.items():
            rv = row.get(k)
            if rv is None:
                return False
            rs = str(rv).strip()[:10]
            hs = str(high).strip()[:10]
            if len(rs) < 10 or len(hs) < 10:
                return False
            if rs > hs:
                return False
        for k, want in filters.items():
            got = row.get(k)
            if got == want:
                continue
            if isinstance(want, bool) and got is want:
                continue
            if str(got) == str(want):
                continue
            return False
        for k, banned in neq.items():
            if str(row.get(k)) == str(banned):
                return False
        for k, allowed in in_filters.items():
            if str(row.get(k)) not in {str(x) for x in allowed}:
                return False
        return True

    def _execute_table_query(self, q: _MemQuery) -> _ExecResult:
        t = q._table
        if t == "bank_transactions":
            return self._exec_bank(q)
        if t == "facturas":
            return self._exec_facturas(q)
        if t == "clientes":
            return self._exec_clientes(q)
        if t == "gastos":
            return self._exec_gastos(q)
        if t == "gastos_vehiculo":
            return self._exec_gastos_vehiculo(q)
        if t == "portes":
            return self._exec_portes(q)
        if t == "empresas":
            return self._exec_empresas(q)
        if t == "profiles":
            return self._exec_profiles(q)
        return _ExecResult([])

    def _exec_empresas(self, q: _MemQuery) -> _ExecResult:
        if q._op != "select":
            return _ExecResult([])
        rows = [
            dict(r)
            for r in self.empresas.values()
            if self._row_matches(
                r,
                filters=q._filters,
                neq=q._neq,
                in_filters=q._in_filters,
                null_if_missing=q._null_if_missing,
                gte=q._gte,
                lte=q._lte,
            )
        ]
        if q._limit is not None:
            rows = rows[: q._limit]
        return _ExecResult(rows)

    def _exec_profiles(self, q: _MemQuery) -> _ExecResult:
        if q._op != "select":
            return _ExecResult([])
        rows = [
            dict(r)
            for r in self.profiles
            if self._row_matches(
                r,
                filters=q._filters,
                neq=q._neq,
                in_filters=q._in_filters,
                null_if_missing=q._null_if_missing,
                gte=q._gte,
                lte=q._lte,
            )
        ]
        if q._limit is not None:
            rows = rows[: q._limit]
        return _ExecResult(rows)

    def _exec_bank(self, q: _MemQuery) -> _ExecResult:
        if q._op == "select":
            rows = [
                dict(r)
                for r in self.bank_transactions
                if self._row_matches(
                    r,
                    filters=q._filters,
                    neq=q._neq,
                    in_filters=q._in_filters,
                    null_if_missing=set(),
                    gte=q._gte,
                    lte=q._lte,
                )
            ]
            if q._order_desc and rows:
                rows.sort(key=lambda r: str(r.get("booked_date") or ""), reverse=True)
            if q._limit is not None:
                rows = rows[: q._limit]
            return _ExecResult(rows)
        if q._op == "update" and q._payload is not None:
            for r in self.bank_transactions:
                if self._row_matches(
                    r,
                    filters=q._filters,
                    neq=q._neq,
                    in_filters=q._in_filters,
                    null_if_missing=set(),
                    gte=q._gte,
                    lte=q._lte,
                ):
                    r.update(dict(q._payload))
                    return _ExecResult([dict(r)])
            return _ExecResult([])
        return _ExecResult([])

    def _exec_facturas(self, q: _MemQuery) -> _ExecResult:
        if q._op == "select":
            rows = [
                dict(r)
                for r in self.facturas
                if self._row_matches(
                    r,
                    filters=q._filters,
                    neq=q._neq,
                    in_filters=q._in_filters,
                    null_if_missing=q._null_if_missing,
                    gte=q._gte,
                    lte=q._lte,
                )
            ]
            if q._limit is not None:
                rows = rows[: q._limit]
            return _ExecResult(rows)
        if q._op == "update" and q._payload is not None:
            for r in self.facturas:
                if self._row_matches(
                    r,
                    filters=q._filters,
                    neq=q._neq,
                    in_filters=q._in_filters,
                    null_if_missing=q._null_if_missing,
                    gte=q._gte,
                    lte=q._lte,
                ):
                    r.update(dict(q._payload))
                    return _ExecResult([dict(r)])
            return _ExecResult([])
        return _ExecResult([])

    def _exec_clientes(self, q: _MemQuery) -> _ExecResult:
        if q._op != "select":
            return _ExecResult([])
        eid = str(q._filters.get("empresa_id") or "")
        if "id" in q._in_filters:
            allowed = {str(x) for x in q._in_filters["id"]}
            out = [dict(r) for r in self.clientes.values() if str(r.get("id")) in allowed and str(r.get("empresa_id")) == eid]
            return _ExecResult(out)
        cid = str(q._filters.get("id") or "")
        row = self.clientes.get(cid)
        if not row or (eid and str(row.get("empresa_id")) != eid):
            return _ExecResult([])
        return _ExecResult([dict(row)])

    def _exec_gastos(self, q: _MemQuery) -> _ExecResult:
        if q._op != "select":
            return _ExecResult([])
        eid = str(q._filters.get("empresa_id") or "")
        rows = [dict(r) for r in self.gastos if str(r.get("empresa_id")) == eid]
        if "deleted_at" in q._null_if_missing:
            rows = [r for r in rows if r.get("deleted_at") is None]
        return _ExecResult(rows)

    def _exec_gastos_vehiculo(self, q: _MemQuery) -> _ExecResult:
        if q._op != "select":
            return _ExecResult([])
        eid = str(q._filters.get("empresa_id") or "")
        rows = [dict(r) for r in self.gastos_vehiculo if str(r.get("empresa_id")) == eid]
        if "deleted_at" in q._null_if_missing:
            rows = [r for r in rows if r.get("deleted_at") is None]
        return _ExecResult(rows)

    def _exec_portes(self, q: _MemQuery) -> _ExecResult:
        if q._op != "select":
            return _ExecResult([])
        rows = [
            dict(r)
            for r in self.portes
            if self._row_matches(
                r,
                filters=q._filters,
                neq=q._neq,
                in_filters=q._in_filters,
                null_if_missing=q._null_if_missing,
                gte=q._gte,
                lte=q._lte,
            )
        ]
        return _ExecResult(rows)

    @property
    def storage(self) -> object:
        return MagicMock()


class _MapsStub(MapsService):
    def __init__(self) -> None:
        pass

    async def get_route_data(self, *_a: object, **_k: object) -> dict[str, Any]:
        return {"distance_km": 100.0, "duration_mins": 60, "source": "stub"}


class _EsgStub:
    def calculate_route_emissions(self, *, distance_km: float) -> float:
        return 0.0


@pytest.fixture
async def banking_recon_client(monkeypatch: pytest.MonkeyPatch):
    """AsyncClient + captura de ``asyncio.create_task`` (middleware de auditoría)."""
    from unittest.mock import AsyncMock

    from app.core.config import get_settings
    from app.main import create_app

    pending: list[asyncio.Task[Any]] = []
    orig_create_task = asyncio.create_task

    def _capture_task(coro: Any) -> asyncio.Task[Any]:
        t = orig_create_task(coro)
        pending.append(t)
        return t

    monkeypatch.setattr(asyncio, "create_task", _capture_task)

    monkeypatch.setenv(
        "GOCARDLESS_SECRET_ID",
        "sandbox_gocardless_secret_id_e2e",
    )
    monkeypatch.setenv(
        "GOCARDLESS_SECRET_KEY",
        "sandbox_gocardless_secret_key_e2e",
    )
    monkeypatch.setenv(
        "GOCARDLESS_ACCESS_TOKEN",
        "sandbox_gocardless_access_token_e2e",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-e2e-banking-reconciliation")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    reset_secret_manager()

    async def _fake_get_supabase(*_a: object, **_k: object) -> BankingReconciliationMemoryDb:
        raise RuntimeError("tests must override get_supabase with the scenario fake")

    monkeypatch.setattr("app.db.supabase.get_supabase", _fake_get_supabase)
    monkeypatch.setattr("app.middleware.tenant_rbac_context.get_supabase", _fake_get_supabase)
    monkeypatch.setattr("app.middleware.audit_log_middleware.get_supabase", _fake_get_supabase)

    monkeypatch.setattr(
        "app.core.health_checks.run_deep_health",
        AsyncMock(
            return_value={
                "status": "healthy",
                "checks": {
                    "supabase": {"ok": True, "detail": "supabase_ok"},
                    "finance_service": {"ok": True, "detail": "finance_ok"},
                },
            },
        ),
    )

    application = create_app()
    try:
        transport = ASGITransport(app=application, lifespan="on")
    except TypeError:
        transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, pending


def _gocardless_fixture_payload(*, description: str, amount_eur: str, booked: str) -> dict[str, Any]:
    """Fixture estilo webhook/recurso GoCardless (importe en céntimos + descripción SEPA)."""
    minor = str(int(Decimal(amount_eur) * 100))
    return {
        "events": [
            {
                "details": {"description": description, "amount": minor},
                "links": {"payment": "PMsandbox123"},
                "metadata": {"reference": "SEPA-QA"},
            }
        ]
    }


@pytest.mark.asyncio
async def test_banking_reconciliation_e2e_ai_match_updates_invoice_kpis_and_audit(
    banking_recon_client: tuple[AsyncClient, list[asyncio.Task[Any]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Concepto con error tipográfico respecto al número de factura → fuzzy en banda IA → LLM desambigua.
    Tras commit: factura COBRADA, tesorería real del mes, auditoría de la petición POST.
    """
    client, pending_tasks = banking_recon_client
    empresa_id = str(EMPRESA_A_ID)
    cliente_id = str(uuid4())
    tx_id = str(uuid4())
    factura_id = 9_001
    invoice_number = "FAC-2026-0100"
    total = Decimal("1210.00")
    booked = "2026-04-15"
    issued = "2026-04-01"
    # Sin el número canónico en texto plano; el fuzzy queda por debajo del umbral AUTO (>0,95).
    bank_description = (
        "INGRESO SEPA Transportes ACME SL ref fac-2026-ol00 cobro abril"
    )

    mem = BankingReconciliationMemoryDb(
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        factura_id=factura_id,
        transaction_id=tx_id,
        invoice_number=invoice_number,
        bank_description=bank_description,
        invoice_total=total,
        booked_date=booked,
        fecha_emision=issued,
    )

    async def _get_db() -> BankingReconciliationMemoryDb:
        return mem

    async def _get_supabase(*_a: object, **_k: object) -> BankingReconciliationMemoryDb:
        return mem

    monkeypatch.setattr("app.db.supabase.get_supabase", _get_supabase)
    monkeypatch.setattr("app.middleware.tenant_rbac_context.get_supabase", _get_supabase)
    monkeypatch.setattr("app.middleware.audit_log_middleware.get_supabase", _get_supabase)

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_db] = _get_db

    def _llm_pick_invoice(self: Any, *, transaction_json: str, candidates_json: str) -> str:
        _ = (transaction_json, candidates_json)
        return json.dumps(
            {
                "factura_id": factura_id,
                "confidence_score": 0.92,
                "razonamiento": "El importe coincide y el concepto corrupto 'ol00' corresponde a '0100' y cliente ACME.",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        "app.services.reconciliation_service.ReconciliationService._llm_bank_orchestrator_sync",
        _llm_pick_invoice,
    )

    bearer = create_access_token(subject="admin@qa.local", empresa_id=empresa_id)
    headers = {"Authorization": f"Bearer {bearer}"}

    match = MatchingService(mem)  # type: ignore[arg-type]
    pre = await match.get_candidates(empresa_id=empresa_id, transaction_id=tx_id)
    assert pre, "debe existir al menos un candidato fuzzy (importe exacto)"
    assert FUZZY_AI_FLOOR < pre[0].score <= FUZZY_AUTO_MATCH_THRESHOLD, (
        "Ajustar descripción bancaria: la suite exige fuzzy en banda IA "
        f"(score={pre[0].score} ref={pre[0].reference_score} date={pre[0].date_score})"
    )

    try:
        res = await client.post(
            "/api/v1/banking/reconcile",
            headers=headers,
            json={
                "commit": True,
                "transaction_id": tx_id,
                "ai_commit_min_confidence": 0.85,
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["orchestration_mode"] == "hybrid"
        assert body["committed_pairs"] == 1
        assert body["hybrid_results"]
        assert body["hybrid_results"][0]["method"] == "ai"

        inv = mem.facturas[0]
        assert str(inv.get("estado_cobro")).lower() == "cobrada"
        assert inv.get("matched_transaction_id") == tx_id
        assert str(inv.get("fecha_cobro_real") or "")[:10] == booked

        bt = mem.bank_transactions[0]
        assert bt.get("reconciled") is True

        for t in pending_tasks:
            try:
                await t
            except Exception:
                pass
        pending_tasks.clear()

        assert mem.audit_rpc_calls, "AuditLogMiddleware → audit_logs_insert_api_event"
        last = mem.audit_rpc_calls[-1]
        assert last.get("p_table_name") == "api_requests"
        assert str(last.get("p_action") or "").upper() == "INSERT"
        nv = last.get("p_new_data") or {}
        assert nv.get("method") == "POST"
        assert "/api/v1/banking/reconcile" in str(nv.get("endpoint") or "")

        sm = get_secret_manager()
        assert (sm.get_gocardless_secret_key() or "").startswith("sandbox_")

        finance = FinanceService(mem)  # type: ignore[arg-type]
        hoy = date(2026, 4, 19)
        dash = await finance.financial_dashboard(empresa_id=empresa_id, hoy=hoy, period_month="2026-04")
        cobros_abril = next(
            (x.cobros_reales for x in dash.tesoreria_mensual if x.periodo == "2026-04"),
            None,
        )
        assert cobros_abril is not None
        assert float(cobros_abril) == pytest.approx(float(total), rel=0, abs=0.01)

        facturas = MagicMock()
        facturas.list_facturas = AsyncMock(return_value=[])
        flota_shim = MagicMock()
        flota_shim._db = mem
        advisor = LogisAdvisorService(
            finance,
            facturas,
            flota_shim,
            _MapsStub(),
            _EsgStub(),
        )
        ctx = await advisor.build_data_context(empresa_id=empresa_id)
        assert ctx["financial_summary"]["margen_neto_por_km_mes_actual"] == dash.margen_neto_km_mes_actual
    finally:
        app.dependency_overrides.pop(deps.get_db, None)


@pytest.mark.asyncio
async def test_banking_reconciliation_e2e_low_confidence_ai_no_auto_commit_manual_review_gate(
    banking_recon_client: tuple[AsyncClient, list[asyncio.Task[Any]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    IA con confianza < umbral de commit (control de riesgos): no persistir; factura sigue pendiente de revisión.
    """
    client, pending_tasks = banking_recon_client
    empresa_id = str(EMPRESA_A_ID)
    cliente_id = str(uuid4())
    tx_id = str(uuid4())
    factura_id = 9_002
    invoice_number = "FAC-2026-0200"
    total = Decimal("850.50")
    mem = BankingReconciliationMemoryDb(
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        factura_id=factura_id,
        transaction_id=tx_id,
        invoice_number=invoice_number,
        bank_description="INGRESO SEPA Transportes ACME SL ref fac-2026-02oo cobro abril",
        invoice_total=total,
        booked_date="2026-04-12",
        fecha_emision="2026-04-02",
    )

    async def _get_db() -> BankingReconciliationMemoryDb:
        return mem

    async def _get_supabase(*_a: object, **_k: object) -> BankingReconciliationMemoryDb:
        return mem

    monkeypatch.setattr("app.db.supabase.get_supabase", _get_supabase)
    monkeypatch.setattr("app.middleware.tenant_rbac_context.get_supabase", _get_supabase)
    monkeypatch.setattr("app.middleware.audit_log_middleware.get_supabase", _get_supabase)

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_db] = _get_db

    def _llm_low_confidence(self: Any, *, transaction_json: str, candidates_json: str) -> str:
        _ = (transaction_json, candidates_json)
        return json.dumps(
            {
                "factura_id": factura_id,
                "confidence_score": 0.62,
                "razonamiento": "Posible coincidencia pero el concepto es demasiado ambiguo; requiere revisión humana.",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        "app.services.reconciliation_service.ReconciliationService._llm_bank_orchestrator_sync",
        _llm_low_confidence,
    )

    match = MatchingService(mem)  # type: ignore[arg-type]
    pre = await match.get_candidates(empresa_id=empresa_id, transaction_id=tx_id)
    assert pre and FUZZY_AI_FLOOR < pre[0].score <= FUZZY_AUTO_MATCH_THRESHOLD

    bearer = create_access_token(subject="admin@qa.local", empresa_id=empresa_id)
    try:
        res = await client.post(
            "/api/v1/banking/reconcile",
            headers={"Authorization": f"Bearer {bearer}"},
            json={
                "commit": True,
                "transaction_id": tx_id,
                "ai_commit_min_confidence": 0.85,
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["committed_pairs"] == 0
        assert body["hybrid_results"]
        hr0 = body["hybrid_results"][0]
        assert hr0["method"] == "ai"
        assert hr0["candidate"] is not None
        assert float(hr0["final_confidence"]) < 0.85

        assert str(mem.facturas[0].get("estado_cobro")).lower() == "emitida"
        assert mem.bank_transactions[0].get("reconciled") is False
    finally:
        for t in pending_tasks:
            try:
                await t
            except Exception:
                pass
        pending_tasks.clear()
        app.dependency_overrides.pop(deps.get_db, None)
