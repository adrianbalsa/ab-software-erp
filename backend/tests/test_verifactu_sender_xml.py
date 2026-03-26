"""XML registro facturación alta (fingerprints y campos fiscales)."""

from __future__ import annotations

from app.services.verifactu_sender import generar_xml_registro_facturacion_alta, interpretar_respuesta_aeat


def test_xml_incluye_huella_y_huella_anterior() -> None:
    xml = generar_xml_registro_facturacion_alta(
        factura={
            "num_factura": "F-2026-001",
            "fecha_emision": "2026-04-01",
            "base_imponible": 100.0,
            "cuota_iva": 21.0,
            "total_factura": 121.0,
            "tipo_factura": "F1",
            "nif_emisor": "B12345678",
        },
        empresa={"nif": "B12345678", "nombre_comercial": "Emp T"},
        cliente={"nif": "A11111111", "nombre": "Cli"},
        hash_registro="aa" * 32,
        fingerprint="bb" * 32,
        prev_fingerprint="cc" * 32,
    )
    assert "bb" * 32 in xml and "<Huella>" in xml
    assert "cc" * 32 in xml and "<HuellaAnterior>" in xml
    assert "aa" * 32 in xml and "<HashRegistro>" in xml
    assert "RegistroFacturacionAltaVeriFactu" in xml


def test_interpretar_http_503() -> None:
    r = interpretar_respuesta_aeat(cuerpo="<xml/>", http_status=503)
    assert r.estado_factura_codigo == "error_tecnico"


def test_interpretar_aceptado() -> None:
    r = interpretar_respuesta_aeat(cuerpo="<Estado>Correcto</Estado>", http_status=200)
    assert r.estado_factura_codigo == "aceptado"
