from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest

sys.modules.setdefault("rapidfuzz", MagicMock(name="rapidfuzz_test_double"))
sys.modules.setdefault("litellm", MagicMock(name="litellm_test_double"))
sys.modules.setdefault("anthropic", MagicMock(name="anthropic_test_double"))

from app.api import deps
from app.schemas.user import UserOut


class _FakeWeasyHTML:
    def __init__(self, string: str) -> None:
        self._string = string

    def write_pdf(self) -> bytes:
        # For QA assertions we return rendered HTML bytes deterministically.
        return self._string.encode("utf-8")


@pytest.mark.asyncio
async def test_reports_efficiency_includes_esg_and_vampire_radar(
    client,
    monkeypatch: pytest.MonkeyPatch,
    mock_user_empresa_a: dict[str, object],
) -> None:
    empresa_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_current_user] = lambda: UserOut(
        username="qa@test.local",
        empresa_id=empresa_id,
        rol="user",
        rbac_role="owner",
        usuario_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    )

    # Mock ESG service requirement: deterministic 150.0 kg for route emissions logic.
    class _FakeEsgService:
        @staticmethod
        def calculate_route_emissions(distance_km: float, factor_co2_km: float = 750.0) -> float:
            _ = (distance_km, factor_co2_km)
            return 150.0

    monkeypatch.setattr("app.services.ai_service.EsgService", _FakeEsgService)

    async def _fake_context(**_kwargs: object) -> dict[str, object]:
        return {
            "ebitda_snapshot": {
                "ingresos_netos_sin_iva_eur": 125000.0,
                "gastos_netos_sin_iva_eur": 82000.0,
                "ebitda_aprox_sin_iva_eur": 43000.0,
            },
            "cashflow_tesoreria": {
                "margen_km_eur": 0.28,
                "km_facturados_mes_actual": 200.0,
            },
            "cip_vampiros": [{"route_ref": "Madrid|Valencia"}],
            "bi_intelligence": {
                "routes_efficiency_below_1": [
                    {
                        "route_label": "Madrid -> Valencia",
                        "cliente_nombre": "Cliente QA",
                        "margin_eur": 1250.5,
                        "km_estimados": 200.0,
                        "efficiency_eta": 0.92,
                    }
                ]
            },
        }

    monkeypatch.setattr("app.api.routes.reports.gather_advisor_context", _fake_context)
    monkeypatch.setattr(
        "app.api.routes.reports.mask_advisor_context_for_rbac",
        lambda ctx, *, rbac_role: ctx,
    )
    monkeypatch.setattr("app.services.report_service.HTML", _FakeWeasyHTML)

    try:
        res = await client.get(
            f"/reports/efficiency/{empresa_id}",
            headers={"Authorization": f"Bearer {mock_user_empresa_a['jwt']}"},
        )
        assert res.status_code == 200
        assert res.headers.get("content-type", "").startswith("application/pdf")

        body = res.content.decode("utf-8")
        assert "Huella de Carbono Total" in body
        assert "150.0 kg" in body
        assert "Nota de Sostenibilidad:" in body
        # Regression: Vampire radar financial row still present.
        assert "Madrid -&gt; Valencia" in body
        assert "1,250.50 EUR" in body
        assert "0.9200" in body
    finally:
        app.dependency_overrides.clear()
