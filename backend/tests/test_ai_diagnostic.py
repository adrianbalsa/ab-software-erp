from __future__ import annotations

import json
import sys
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest

# Optional dependency imported transitively by app.api.deps in this test env.
sys.modules.setdefault("litellm", MagicMock(name="litellm_test_double"))
sys.modules.setdefault("anthropic", MagicMock(name="anthropic_test_double"))

from app.api import deps
from app.core.constants import COSTE_OPERATIVO_EUR_KM
from app.schemas.user import UserOut
from app.services.ai_service import LogisAdvisorService


class _FakeQuery:
    def __init__(self, table_name: str) -> None:
        self.table_name = table_name

    def select(self, *_args: object) -> _FakeQuery:
        return self

    def eq(self, *_args: object) -> _FakeQuery:
        return self

    def order(self, *_args: object, **_kwargs: object) -> _FakeQuery:
        return self

    def limit(self, *_args: object) -> _FakeQuery:
        return self

    def execute(self) -> object:
        data: list[dict[str, object]]
        if self.table_name == "portes":
            data = [
                {
                    "id": "porte-1",
                    "origen": "Madrid",
                    "destino": "Valencia",
                    "precio_pactado": 100.0,
                    "km_estimados": 200.0,
                    "estado": "pendiente",
                    "fecha": "2026-04-14",
                }
            ]
        elif self.table_name == "facturas":
            data = []
        else:
            data = []
        return SimpleNamespace(data=data)


class _FakeDb:
    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(name)

    async def execute(self, query: object) -> object:
        return query.execute()


class _FakeMapsService:
    async def get_route_data(
        self,
        _origin: str,
        _destination: str,
        **_kwargs: object,
    ) -> dict[str, object]:
        return {
            "distance_km": 200.0,
            "duration_mins": 130,
            "source": "mocked_maps",
        }


def _make_service() -> LogisAdvisorService:
    finance = SimpleNamespace(
        financial_summary=lambda empresa_id: None,
        financial_dashboard=lambda empresa_id: None,
    )
    facturas = SimpleNamespace(list_facturas=lambda empresa_id: None)
    flota = SimpleNamespace(_db=_FakeDb())
    esg = SimpleNamespace(calculate_route_emissions=lambda distance_km: 0.0)
    maps = _FakeMapsService()
    return LogisAdvisorService(
        finance=finance,  # type: ignore[arg-type]
        facturas=facturas,  # type: ignore[arg-type]
        flota=flota,  # type: ignore[arg-type]
        maps=maps,  # type: ignore[arg-type]
        esg=esg,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_prepare_ai_context_eta_and_vampire_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _make_service()

    async def _financial_summary(*, empresa_id: str) -> object:
        _ = empresa_id
        return SimpleNamespace(ingresos=5000.0, gastos=3000.0, ebitda=2000.0)

    async def _list_facturas(*, empresa_id: str) -> list[object]:
        _ = empresa_id
        return [SimpleNamespace(estado_cobro="pendiente", fecha_emision=date(2026, 2, 1))]

    monkeypatch.setattr(service._finance, "financial_summary", _financial_summary)
    monkeypatch.setattr(service._facturas, "list_facturas", _list_facturas)

    payload = json.loads(await service.prepare_ai_context(empresa_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    route = payload["operational"]["active_routes"][0]

    op_cost = 200.0 * float(COSTE_OPERATIVO_EUR_KM)
    eta_expected = round(100.0 / op_cost, 4)
    assert round(float(route["efficiency_eta"]), 3) == round(eta_expected, 3)
    assert route["vampire_route"] is True


@pytest.mark.asyncio
async def test_api_consult_returns_structured_json_and_redacts_sensitive_context(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _make_service()

    async def _financial_summary(*, empresa_id: str) -> object:
        _ = empresa_id
        return SimpleNamespace(ingresos=5000.0, gastos=3000.0, ebitda=2000.0)

    async def _financial_dashboard(*, empresa_id: str) -> object:
        _ = empresa_id
        return SimpleNamespace(margen_neto_km_mes_actual=0.12)

    async def _list_facturas(*, empresa_id: str) -> list[object]:
        _ = empresa_id
        return [SimpleNamespace(estado_cobro="pendiente", fecha_emision=date(2026, 2, 1))]

    monkeypatch.setattr(service._finance, "financial_summary", _financial_summary)
    monkeypatch.setattr(service._finance, "financial_dashboard", _financial_dashboard)
    monkeypatch.setattr(service._facturas, "list_facturas", _list_facturas)
    from app.services.secret_manager_service import reset_secret_manager

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reset_secret_manager()

    captured_prompt: dict[str, str] = {}

    async def _fake_litellm_completion(**kwargs):
        messages = kwargs.get("messages") or []
        if len(messages) > 1 and isinstance(messages[1], dict):
            captured_prompt["prompt"] = str(messages[1].get("content") or "")
        content = json.dumps(
            {
                "summary_headline": "Diagnóstico QA",
                "profitability": {"status": "warning", "findings": ["margen bajo"], "actions": ["subir tarifa"]},
                "fiscal_safety": {"status": "ok", "findings": [], "actions": []},
                "liquidity": {"status": "ok", "findings": [], "actions": []},
                "risk_flags": ["vampire_route"],
                "recommended_actions": ["renegociar ruta"],
            },
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    monkeypatch.setattr("app.services.ai_service.litellm.acompletion", _fake_litellm_completion)

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_logis_advisor_service] = lambda: service
    app.dependency_overrides[deps.get_current_user] = lambda: UserOut(
        username="qa@test.local",
        empresa_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        rol="user",
        rbac_role="owner",
        usuario_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    )

    try:
        res = await client.post("/ai/consult", json={"query": "Diagnóstico rápido"})
        assert res.status_code == 200
        body = res.json()
        assert body["profitability"]["status"] == "warning"
        assert "liquidity" in body
        assert "fiscal_safety" in body
        assert "recommended_actions" in body
        # Privacy: the data context sent to AI must not leak identifiable customer fields.
        assert "cliente_nombre" not in captured_prompt.get("prompt", "")
    finally:
        app.dependency_overrides.clear()
