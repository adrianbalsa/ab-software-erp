from __future__ import annotations

import pytest

from app.api import deps


class _MockMapsService:
    async def get_truck_route(
        self,
        origin: str,
        destination: str,
        *,
        emission_type: str | None = None,
        waypoints: list[str] | None = None,
        **_kwargs: object,
    ) -> dict[str, object]:
        assert origin
        assert destination
        assert emission_type is not None
        if waypoints:
            return {
                "distancia_km": 120.0,
                "tiempo_estimado_min": 115,
                "tiene_peajes": True,
                "peajes_estimados_eur": 18.75,
            }
        return {
            "distancia_km": 100.0,
            "tiempo_estimado_min": 90,
            "tiene_peajes": True,
            "peajes_estimados_eur": 12.40,
        }


@pytest.mark.asyncio
async def test_optimize_route_returns_cost_fields(client) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_maps_service] = lambda: _MockMapsService()
    try:
        res = await client.post(
            "/api/v1/routes/optimize-route",
            json={"origen": "Madrid", "destino": "Barcelona"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["ruta_recomendada"] is not None
        ruta = body["ruta_recomendada"]
        assert "fuel_cost_estimate" in ruta
        assert "peajes_estimados_eur" in ruta
        assert "total_route_cost" in ruta
        assert pytest.approx(ruta["fuel_cost_estimate"] + ruta["peajes_estimados_eur"], abs=0.01) == ruta[
            "total_route_cost"
        ]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_optimize_route_waypoints_preserves_cost_invariant(client) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_maps_service] = lambda: _MockMapsService()
    try:
        res = await client.post(
            "/api/v1/routes/optimize-route",
            json={
                "origen": "Valencia",
                "destino": "Bilbao",
                "waypoints": [
                    {"address": "Zaragoza", "order": 0},
                ],
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        rutas = body["rutas"]
        assert len(rutas) == 2
        for ruta in rutas:
            assert isinstance(ruta["fuel_cost_estimate"], float)
            assert isinstance(ruta["peajes_estimados_eur"], float)
            assert isinstance(ruta["total_route_cost"], float)
            assert pytest.approx(ruta["fuel_cost_estimate"] + ruta["peajes_estimados_eur"], abs=0.01) == ruta[
                "total_route_cost"
            ]
    finally:
        app.dependency_overrides.clear()

