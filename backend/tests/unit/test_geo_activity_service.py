from __future__ import annotations

from uuid import UUID

from app.models.enums import UserRole
from app.schemas.user import UserOut
from app.services.geo_activity_service import _build_heatmap_cells, _geo_bucket, _margen_visible


def test_geo_bucket_rounds() -> None:
    assert _geo_bucket(40.123456, -3.987654) == (40.12, -3.99)


def test_build_heatmap_cells_ticket_medio() -> None:
    rows = [
        {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "lat_dest": 40.12, "lng_dest": -3.71},
        {"id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "lat_dest": 40.119, "lng_dest": -3.709},
    ]
    gastos = {
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa": 50.0,
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb": 30.0,
    }
    cells = _build_heatmap_cells(rows, gastos)
    assert len(cells) == 1
    c = cells[0]
    assert c.portes_en_celda == 2
    assert c.ticket_gasto_medio == 40.0
    assert c.intensidad == 1.0


def test_margen_visible_traffic_manager_hidden() -> None:
    u = UserOut(
        username="tm",
        empresa_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        role=UserRole.GESTOR,
        rbac_role="traffic_manager",
    )
    assert _margen_visible(u) is False


def test_margen_visible_owner() -> None:
    u = UserOut(
        username="o",
        empresa_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        role=UserRole.ADMIN,
        rbac_role="owner",
    )
    assert _margen_visible(u) is True
