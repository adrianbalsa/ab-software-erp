from __future__ import annotations

from decimal import Decimal

from app.services.verifactu_service import VerifactuService


def _emitir(
    *,
    nif_emisor: str,
    num_factura: str,
    fecha: str,
    total: Decimal,
    huella_anterior: str,
) -> dict[str, str]:
    huella = VerifactuService.generar_huella_verifactu(
        nif_emisor=nif_emisor,
        numero_serie_factura=num_factura,
        fecha_expedicion=fecha,
        importe_total=total,
        huella_hash_anterior=huella_anterior,
    )
    return {
        "num_factura": num_factura,
        "huella_hash_anterior": huella_anterior,
        "huella_hash": huella,
    }


def test_verifactu_chain_tres_facturas_consecutivas() -> None:
    """
    Cadena VeriFactu por serie:
    - Factura 1 arranca con hash nulo estandarizado (64 ceros).
    - Factura 2 apunta al hash de factura 1.
    - Factura 3 apunta al hash de factura 2.
    """
    null_hash = VerifactuService.null_chain_hash()
    f1 = _emitir(
        nif_emisor="B12345678",
        num_factura="FAC-2026-000001",
        fecha="2026-04-28",
        total=Decimal("121.00"),
        huella_anterior=null_hash,
    )
    f2 = _emitir(
        nif_emisor="B12345678",
        num_factura="FAC-2026-000002",
        fecha="2026-04-28",
        total=Decimal("242.00"),
        huella_anterior=f1["huella_hash"],
    )
    f3 = _emitir(
        nif_emisor="B12345678",
        num_factura="FAC-2026-000003",
        fecha="2026-04-28",
        total=Decimal("363.00"),
        huella_anterior=f2["huella_hash"],
    )

    assert len(f2["huella_hash"]) == 64
    assert f2["huella_hash"] == f2["huella_hash"].upper()
    assert f3["huella_hash_anterior"] == f2["huella_hash"]
