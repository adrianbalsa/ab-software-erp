"""XML registro facturación alta (SuministroLR: Cabecera, RegistroFactura, RegistroAlta)."""

from __future__ import annotations

import re

from app.services.aeat_client_py.xsd_validate import validate_reg_factu_payload_against_suministro_lr_xsd
from app.services.aeat_client_py.zeep_client import default_aeat_suministro_lr_xsd_url
from app.services.suministro_lr_xml import RegistroAnteriorAEAT
from app.services.verifactu_sender import generar_xml_registro_facturacion_alta, interpretar_respuesta_aeat


def test_xml_incluye_huella_y_encadenamiento_registro_anterior() -> None:
    prev_huella = "cc" * 32
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
        prev_fingerprint=prev_huella,
        registro_anterior=RegistroAnteriorAEAT(
            id_emisor_factura="B12345678",
            num_serie_factura="F-2026-000",
            fecha_expedicion="31-03-2026",
            huella=prev_huella,
        ),
    )
    assert "bb" * 32 in xml
    assert "Huella" in xml
    assert "<Cabecera" in xml or "Cabecera" in xml
    assert "ObligadoEmision" in xml
    assert "RegistroFactura" in xml
    assert "RegistroAlta" in xml
    assert "RegistroAnterior" in xml
    assert prev_huella in xml


def test_xml_generado_valida_contra_suministro_lr_xsd() -> None:
    xml_decl = generar_xml_registro_facturacion_alta(
        factura={
            "num_factura": "XSD-1",
            "fecha_emision": "2026-01-15",
            "base_imponible": 10.0,
            "cuota_iva": 2.1,
            "total_factura": 12.1,
            "tipo_factura": "F1",
            "nif_emisor": "B99887766",
        },
        empresa={"nif": "B99887766", "nombre_comercial": "Emp XSD"},
        cliente={"nif": "A11222333", "nombre": "Cli"},
        hash_registro="aa" * 32,
        fingerprint="bb" * 32,
        prev_fingerprint=None,
        registro_anterior=None,
    )
    inner = re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", xml_decl.strip(), count=1)
    validate_reg_factu_payload_against_suministro_lr_xsd(
        reg_factu_inner_xml=inner,
        schema_location=default_aeat_suministro_lr_xsd_url(),
    )


def test_interpretar_http_503() -> None:
    r = interpretar_respuesta_aeat(cuerpo="<xml/>", http_status=503)
    assert r.estado_factura_codigo == "error_tecnico"


def test_interpretar_aceptado() -> None:
    r = interpretar_respuesta_aeat(cuerpo="<Estado>Correcto</Estado>", http_status=200)
    assert r.estado_factura_codigo == "aceptado"
