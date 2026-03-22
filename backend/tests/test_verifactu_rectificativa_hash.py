"""Cadena de hash: compatibilidad F1 vs ampliación R1 [cite: 2026-03-22]."""

from __future__ import annotations

from app.services.verifactu_service import VerifactuService


def test_generar_hash_sin_campos_rect_igual_que_legacy() -> None:
    """Sin tipo ni RECT la cadena coincide con el algoritmo histórico."""
    h = VerifactuService.generar_hash_factura(
        nif_empresa="b12345678",
        nif_cliente="a87654321",
        num_factura="FAC-2025-000001",
        fecha="2025-03-22",
        total=121.0,
        hash_anterior="ab" * 32,
    )
    assert len(h) == 64
    h2 = VerifactuService.generar_hash_factura(
        nif_empresa="b12345678",
        nif_cliente="a87654321",
        num_factura="FAC-2025-000001",
        fecha="2025-03-22",
        total=121.0,
        hash_anterior="ab" * 32,
        tipo_factura=None,
        num_factura_rectificada=None,
    )
    assert h == h2


def test_generar_hash_r1_incluye_tipo_y_rect_distinto() -> None:
    h_f1 = VerifactuService.generar_hash_factura(
        nif_empresa="B1",
        nif_cliente="C1",
        num_factura="R-2025-000002",
        fecha="2025-03-22",
        total=-121.0,
        hash_anterior="cd" * 32,
    )
    h_r1 = VerifactuService.generar_hash_factura(
        nif_empresa="B1",
        nif_cliente="C1",
        num_factura="R-2025-000002",
        fecha="2025-03-22",
        total=-121.0,
        hash_anterior="cd" * 32,
        tipo_factura="R1",
        num_factura_rectificada="FAC-2025-000001",
    )
    assert h_f1 != h_r1
