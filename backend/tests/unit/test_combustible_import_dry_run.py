"""Importación combustible: modo simulación (dry_run) sin persistencia."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.combustible_service import importar_combustible_csv


@pytest.mark.asyncio
async def test_importar_combustible_csv_dry_run_no_create_gasto() -> None:
    csv_bytes = b"Fecha;Matricula;Litros;Importe_Total\n2025-01-15;1234ABC;10.5;42.00\n"

    flota_resp = MagicMock()
    flota_resp.data = [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "matricula": "1234 ABC",
            "certificacion_emisiones": "EURO_VI",
            "odometro_actual": 1000,
        }
    ]

    db = MagicMock()
    db.table.return_value = db
    db.select.return_value = db
    db.eq.return_value = db
    db.execute = AsyncMock(return_value=flota_resp)

    gastos = MagicMock()
    gastos.create_gasto = AsyncMock()

    out = await importar_combustible_csv(
        raw=csv_bytes,
        filename="t.csv",
        empresa_id="emp-1",
        username_empleado="tester",
        db=db,
        gastos_service=gastos,
        dry_run=True,
    )

    assert out.dry_run is True
    assert out.co2_es_estimacion is True
    assert out.filas_importadas_ok == 1
    assert out.total_filas_leidas == 1
    assert out.total_litros == pytest.approx(10.5)
    assert out.total_euros == pytest.approx(42.0)
    assert out.total_co2_kg == pytest.approx(10.5 * 2.67, rel=1e-5)
    assert not out.errores
    gastos.create_gasto.assert_not_called()


@pytest.mark.asyncio
async def test_importar_combustible_csv_dry_run_structured_error_unknown_plate() -> None:
    csv_bytes = b"Fecha;Matricula;Litros;Importe_Total\n2025-01-15;ZZZZ99;1;1\n"

    flota_resp = MagicMock()
    flota_resp.data = []

    db = MagicMock()
    db.table.return_value = db
    db.select.return_value = db
    db.eq.return_value = db
    db.execute = AsyncMock(return_value=flota_resp)

    gastos = MagicMock()
    gastos.create_gasto = AsyncMock()

    out = await importar_combustible_csv(
        raw=csv_bytes,
        filename="t.csv",
        empresa_id="emp-1",
        username_empleado="tester",
        db=db,
        gastos_service=gastos,
        dry_run=True,
    )

    assert out.filas_importadas_ok == 0
    assert len(out.errores) == 1
    assert len(out.errores_detalle) == 1
    assert out.errores_detalle[0].code == "PLATE_NOT_IN_FLEET"
    assert out.errores_detalle[0].row == 1
    gastos.create_gasto.assert_not_called()
