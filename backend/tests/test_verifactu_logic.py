"""
Suite crítica VeriFactu: F1 (hash), inmutabilidad (sin borrado), R1 (rectificativa).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.schemas.factura import FacturaCreateFromPortes
from app.services.facturas_service import FacturasService
from app.services.verifactu_service import VERIFACTU_INVOICE_GENESIS_HASH, VerifactuService


def _data(rows: list[object]) -> SimpleNamespace:
    return SimpleNamespace(data=rows)


@pytest.mark.asyncio
async def test_emitir_f1_genera_hash_registro_correcto() -> None:
    """F1: el hash_registro coincide con la huella VeriFactu determinista."""
    eid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cid = "22222222-2222-2222-2222-222222222222"
    porte_id = "11111111-1111-1111-1111-111111111111"

    fixed = date(2026, 3, 19)
    expected_hash = VerifactuService.generate_invoice_hash(
        {
            "num_factura": "FAC-2026-000001",
            "fecha_emision": fixed.isoformat(),
            "nif_emisor": "B12345678",
            "total_factura": 121.0,
        },
        VERIFACTU_INVOICE_GENESIS_HASH,
    )

    porte_row = {
        "id": porte_id,
        "fecha": fixed.isoformat(),
        "origen": "MAD",
        "destino": "BCN",
        "descripcion": None,
        "precio_pactado": 100.0,
        "bultos": 1,
        "km_estimados": 10.0,
    }
    cliente_det = {
        "id": cid,
        "empresa_id": eid,
        "nombre": "Cliente QA",
        "nif": "A87654321",
        "email": None,
        "telefono": None,
        "direccion": None,
        "deleted_at": None,
    }
    factura_row = {
        "id": 1,
        "empresa_id": eid,
        "cliente": cid,
        "tipo_factura": "F1",
        "num_factura": "FAC-2026-000001",
        "numero_factura": "FAC-2026-000001",
        "nif_emisor": "B12345678",
        "total_factura": 121.0,
        "base_imponible": 100.0,
        "cuota_iva": 21.0,
        "fecha_emision": fixed.isoformat(),
        "numero_secuencial": 1,
        "hash_anterior": VERIFACTU_INVOICE_GENESIS_HASH,
        "hash_registro": expected_hash,
        "hash_factura": expected_hash,
        "bloqueado": True,
        "is_finalized": False,
        "porte_lineas_snapshot": [],
        "total_km_estimados_snapshot": 10.0,
    }

    exec_responses = [
        _data([porte_row]),
        _data([{"nif": "B12345678"}]),
        _data([{"nif": "a87654321"}]),
        _data([{"plan_type": "starter"}]),  # fetch_empresa_plan (antes del encadenamiento)
        _data([]),  # cadena: última factura por empresa
        _data([]),  # huella: último fingerprint_hash (vacío → génesis)
        _data([factura_row]),  # insert facturas
        _data([{}]),
        _data([{}]),
        _data([cliente_det]),
        _data([{}]),  # auditoría (try_log)
        _data([{"nombre_comercial": "Emp QA", "nif": "B12345678"}]),
        _data([{"nombre": "Cliente QA"}]),
    ]

    db = MagicMock()
    db.table = MagicMock(return_value=MagicMock())
    db.execute = AsyncMock(side_effect=exec_responses)
    db.storage_upload = AsyncMock(return_value=None)

    svc = FacturasService(db)
    payload = FacturaCreateFromPortes(cliente_id=UUID(cid), iva_porcentaje=21.0)

    with patch("app.services.facturas_service.get_engine", return_value=None):
        with patch("app.services.facturas_service.date") as mock_date:
            mock_date.today.return_value = fixed
            result = await svc.generar_desde_portes(empresa_id=eid, payload=payload, usuario_id="qa")

    assert result.factura.hash_registro == expected_hash
    assert len(expected_hash) == 64
    assert db.execute.await_count == 13


@pytest.mark.asyncio
async def test_borrar_factura_dispara_trigger_y_es_ignorado_en_compensacion() -> None:
    """
    Simula trigger PG que impide DELETE: la compensación interna no debe propagar el error
    (best-effort; la factura inmutable sigue en sistema).
    """
    db = MagicMock()
    db.table = MagicMock(return_value=MagicMock())

    async def boom(*_a: object, **_k: object) -> SimpleNamespace:
        raise RuntimeError("VeriFactu: DELETE bloqueado por trigger de inmutabilidad")

    db.execute = AsyncMock(side_effect=boom)
    svc = FacturasService(db)
    await svc._eliminar_factura_compensacion(factura_id=99)
    db.execute.assert_awaited()


@pytest.mark.asyncio
async def test_no_delete_http_facturas(client) -> None:
    """Sin JWT no hay borrado (403 middleware); con ruta inexistente / método no expuesto, 404/405."""
    res = await client.delete("/facturas/1")
    assert res.status_code in (403, 404, 405)


@pytest.mark.asyncio
async def test_emitir_r1_rectificativa_vincula_f1_e_importes_negativos() -> None:
    """R1: factura_rectificada_id = F1; totales negativos."""
    eid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cid = "22222222-2222-2222-2222-222222222222"
    fid = 1
    hash_f1 = "c3" * 32

    fixed = date(2026, 3, 19)
    orig = {
        "id": fid,
        "empresa_id": eid,
        "tipo_factura": "F1",
        "hash_registro": hash_f1,
        "hash_factura": hash_f1,
        "cliente": cid,
        "nif_emisor": "B12345678",
        "base_imponible": 100.0,
        "cuota_iva": 21.0,
        "total_factura": 121.0,
        "num_factura": "FAC-2026-000001",
        "porte_lineas_snapshot": [
            {
                "porte_id": "p1",
                "precio_pactado": 100.0,
                "km_estimados": 0.0,
                "fecha": fixed.isoformat(),
                "origen": "A",
                "destino": "B",
                "descripcion": None,
                "bultos": 1,
            }
        ],
        "total_km_estimados_snapshot": 0.0,
        "numero_secuencial": 1,
    }

    chain_row = {
        "hash_registro": hash_f1,
        "hash_factura": hash_f1,
        "numero_secuencial": 1,
        "fecha_emision": fixed.isoformat(),
    }

    r1_row = {
        "id": 2,
        "empresa_id": eid,
        "cliente": cid,
        "tipo_factura": "R1",
        "factura_rectificada_id": fid,
        "total_factura": -121.0,
        "base_imponible": -100.0,
        "cuota_iva": -21.0,
        "num_factura": "R-2026-000002",
        "numero_factura": "R-2026-000002",
        "fecha_emision": fixed.isoformat(),
        "hash_registro": "ff" * 32,
        "hash_factura": "ff" * 32,
        "hash_anterior": hash_f1,
        "numero_secuencial": 2,
        "motivo_rectificacion": "Error en base imponible",
        "porte_lineas_snapshot": [],
        "bloqueado": True,
        "is_finalized": False,
    }

    exec_responses = [
        _data([orig]),
        _data([]),
        _data([{"nif": "A87654321", "nombre": "Cliente QA"}]),
        _data(
            [
                {
                    "nif": "B12345678",
                    "nombre_comercial": "Empresa QA",
                    "nombre_legal": "Empresa QA SL",
                }
            ]
        ),
        _data([chain_row]),
        _data([]),  # huella: último fingerprint_hash
        _data([r1_row]),
        _data([{}]),
        _data([{}]),
    ]

    db = MagicMock()
    db.table = MagicMock(return_value=MagicMock())
    db.execute = AsyncMock(side_effect=exec_responses)

    svc = FacturasService(db)

    with patch("app.services.facturas_service.get_engine", return_value=None):
        with patch("app.services.facturas_service.date") as mock_date:
            mock_date.today.return_value = fixed
            out = await svc.emitir_factura_rectificativa(
                empresa_id=eid,
                factura_id=fid,
                motivo="Error en base imponible",
                usuario_id="qa",
            )

    assert out.factura_rectificada_id == fid
    assert out.total_factura < 0
    assert out.base_imponible < 0
    assert out.cuota_iva < 0
    assert out.tipo_factura == "R1"
