from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.bi import BiDashboardSummaryOut, BiProfitabilityChartsOut, ProfitabilityScatterPoint


def test_logis_advisor_bi_append_in_system_prompt() -> None:
    from app.services import advisor_service as adv

    assert "bi_intelligence" in adv.LOGIS_ADVISOR_BI_APPEND
    assert "liquidez" in adv.LOGIS_ADVISOR_BI_APPEND.lower()
    assert "clientes_presion_cobro" in adv.LOGIS_ADVISOR_BI_APPEND
    assert "η" in adv.LOGIS_ADVISOR_BI_APPEND or "efficiency_eta" in adv.LOGIS_ADVISOR_BI_APPEND
    assert adv.LOGIS_ADVISOR_BI_APPEND.strip() in adv.LOGIS_ADVISOR_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_build_bi_intelligence_routes_eta_below_one() -> None:
    from app.services.advisor_service import _build_bi_intelligence

    pid = uuid4()
    mock_bi = MagicMock()
    mock_bi.dashboard_summary = AsyncMock(
        return_value=BiDashboardSummaryOut(
            dso_days=45.0,
            dso_sample_size=4,
            avg_margin_eur=200.0,
            avg_margin_portes=10,
            total_co2_saved_kg=120.0,
            co2_saved_portes=8,
            avg_efficiency_eur_per_eur_km=1.05,
            efficiency_sample_size=10,
        )
    )
    mock_bi.profitability_scatter = AsyncMock(
        return_value=BiProfitabilityChartsOut(
            points=[
                ProfitabilityScatterPoint(
                    porte_id=pid,
                    km=100.0,
                    margin_eur=-50.0,
                    precio_pactado=12.0,
                    route_label="Madrid → Valencia",
                    cliente="Carga Sur",
                ),
            ],
            coste_operativo_eur_km=0.62,
        )
    )
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(data=[]))

    out = await _build_bi_intelligence(
        db=mock_db,
        empresa_id="00000000-0000-4000-8000-000000000001",
        bi=mock_bi,
    )

    assert "error" not in out
    assert out["dashboard_summary"]["dso_days"] == 45.0
    assert out["routes_efficiency_below_1_total"] == 1
    assert out["routes_efficiency_below_1"][0]["efficiency_eta"] < 1.0
    assert out["routes_efficiency_below_1"][0]["route_label"] == "Madrid → Valencia"
    mock_bi.dashboard_summary.assert_awaited_once()
    mock_bi.profitability_scatter.assert_awaited_once()


def test_mask_hides_bi_intelligence_for_traffic_manager() -> None:
    from app.services.advisor_service import mask_advisor_context_for_rbac

    ctx: dict = {
        "ebitda_snapshot": {"ingresos_netos_sin_iva_eur": 1.0},
        "bi_intelligence": {"dashboard_summary": {"dso_days": 30.0}},
    }
    out = mask_advisor_context_for_rbac(ctx, rbac_role="traffic_manager")
    assert out["bi_intelligence"].get("masked_for_role") is True
