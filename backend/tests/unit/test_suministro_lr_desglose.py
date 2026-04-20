"""RegistroAlta / Desglose multi-IVA, RE y exención (XSD AEAT local)."""

from __future__ import annotations

from decimal import Decimal

from app.core.fiscal_logic import fiscal_amount_string_two_decimals
from app.core.verifactu_hashing import VerifactuCadena, generar_hash_factura_oficial
from app.services.aeat_client_py.xsd_validate import validate_reg_factu_payload_against_suministro_lr_xsd
from app.services.aeat_client_py.zeep_client import default_aeat_suministro_lr_xsd_url
from app.services.suministro_lr_xml import inner_xml_fragment_unsigned_alta_for_tests


def _validate(inner: str) -> None:
    validate_reg_factu_payload_against_suministro_lr_xsd(
        reg_factu_inner_xml=inner,
        schema_location=default_aeat_suministro_lr_xsd_url(),
    )


def test_fiscal_amount_two_decimals_no_float_drift() -> None:
    assert fiscal_amount_string_two_decimals(Decimal("121.00")) == "121.00"
    assert fiscal_amount_string_two_decimals(Decimal("111.20")) == "111.20"
    assert fiscal_amount_string_two_decimals("100") == "100.00"


def test_generar_hash_factura_oficial_emision_decimal_coherente() -> None:
    h1 = generar_hash_factura_oficial(
        VerifactuCadena.HUELLA_EMISION,
        {"num_factura": "A", "fecha_emision": "2026-01-01", "total_factura": Decimal("121.00")},
        "0" * 64,
    )
    h2 = generar_hash_factura_oficial(
        VerifactuCadena.HUELLA_EMISION,
        {"num_factura": "A", "fecha_emision": "2026-01-01", "total_factura": "121.00"},
        "0" * 64,
    )
    assert h1 == h2


def test_xsd_re_multii_va() -> None:
    inner = inner_xml_fragment_unsigned_alta_for_tests(
        factura={
            "num_factura": "XSD-RE",
            "fecha_emision": "2026-04-17",
            "total_factura": Decimal("111.20"),
            "tipo_factura": "F1",
            "nif_emisor": "B12345678",
            "desglose_por_tipo": [
                {
                    "tipo_iva_porcentaje": "21.00",
                    "base_imponible": "100.00",
                    "cuota_iva": "21.00",
                    "cuota_recargo_equivalencia": "5.20",
                }
            ],
        },
        empresa={"nif": "B12345678", "nombre_comercial": "Emp"},
        cliente={"nif": "A11111111", "nombre": "Cli"},
        fingerprint="ab" * 32,
        registro_anterior=None,
    )
    assert "TipoRecargoEquivalencia" in inner and "5.20" in inner and "111.20" in inner
    _validate(inner)


def test_xsd_exenta_e1() -> None:
    inner = inner_xml_fragment_unsigned_alta_for_tests(
        factura={
            "num_factura": "XSD-E1",
            "fecha_emision": "2026-04-17",
            "total_factura": "25.00",
            "tipo_factura": "F1",
            "nif_emisor": "B12345678",
            "desglose_por_tipo": [
                {
                    "tipo_iva_porcentaje": "0.00",
                    "base_imponible": "25.00",
                    "cuota_iva": "0.00",
                    "motivo_exencion": "E1",
                }
            ],
        },
        empresa={"nif": "B12345678", "nombre_comercial": "Emp"},
        cliente={"nif": "A11111111", "nombre": "Cli"},
        fingerprint="ab" * 32,
        registro_anterior=None,
    )
    assert "OperacionExenta" in inner and "E1" in inner
    _validate(inner)


def test_xsd_no_sujeto_n1() -> None:
    inner = inner_xml_fragment_unsigned_alta_for_tests(
        factura={
            "num_factura": "XSD-N1",
            "fecha_emision": "2026-04-17",
            "total_factura": "100.00",
            "tipo_factura": "F1",
            "nif_emisor": "B12345678",
            "desglose_por_tipo": [
                {
                    "tipo_iva_porcentaje": "0.00",
                    "base_imponible": "100.00",
                    "cuota_iva": "0.00",
                    "tipo_no_sujecion": "N1",
                }
            ],
        },
        empresa={"nif": "B12345678", "nombre_comercial": "Emp"},
        cliente={"nif": "A11111111", "nombre": "Cli"},
        fingerprint="ab" * 32,
        registro_anterior=None,
    )
    assert "N1" in inner
    _validate(inner)
