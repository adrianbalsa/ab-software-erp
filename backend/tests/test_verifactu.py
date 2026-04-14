"""
Flujo fiscal VeriFactu: firma XAdES-BES (signxml) + respuesta AEAT simulada sin red.

Valida que el XML de registro se firma correctamente y que el pipeline HTTP
(httpx.MockTransport) entrega una respuesta tipo AEAT que ``interpretar_respuesta_aeat``
clasifica sin contactar con Hacienda.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.core.xades_signer import sign_xml_xades
from app.services.suministro_lr_xml import RegistroAnteriorAEAT
from app.services.suministro_lr_xml import build_registro_alta_unsigned
from app.services.suministro_lr_xml import inner_xml_fragment_from_signed_registro_alta
from app.services.verifactu_sender import envolver_soap12, interpretar_respuesta_aeat
from lxml import etree


def _certificado_y_clave_pem() -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-verifactu-pipeline")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def test_generar_xml_registro_y_firma_xades_contiene_signatura() -> None:
    prev_h = "cc" * 32
    alta_u = build_registro_alta_unsigned(
        factura={
            "num_factura": "F-2026-042",
            "fecha_emision": "2026-04-01",
            "base_imponible": 100.0,
            "cuota_iva": 21.0,
            "total_factura": 121.0,
            "tipo_factura": "F1",
            "nif_emisor": "B12345678",
        },
        empresa={"nif": "B12345678", "nombre_comercial": "Empresa Test SL"},
        cliente={"nif": "A11111111", "nombre": "Cliente Test"},
        fingerprint="bb" * 32,
        registro_anterior=RegistroAnteriorAEAT(
            id_emisor_factura="B12345678",
            num_serie_factura="F-2026-041",
            fecha_expedicion="31-03-2026",
            huella=prev_h,
        ),
        rectificada=None,
    )
    cert_pem, key_pem = _certificado_y_clave_pem()
    alta_xml = etree.tostring(alta_u, xml_declaration=True, encoding="utf-8")
    signed = sign_xml_xades(alta_xml, cert_pem, key_pem, None)
    inner = inner_xml_fragment_from_signed_registro_alta(
        empresa={"nif": "B12345678", "nombre_comercial": "Empresa Test SL"},
        factura={"nif_emisor": "B12345678"},
        signed_registro_alta_xml=signed,
    )
    assert "Cabecera" in inner and "RegistroFactura" in inner
    assert b"ds:Signature" in signed or b"Signature" in signed
    assert b"http://uri.etsi.org/01903/v1.3.2#" in signed


@pytest.mark.asyncio
async def test_soap_firmado_post_mock_aeat_sin_red_interpreta_aceptado() -> None:
    """Simula POST SOAP tras firma; el handler valida que el cuerpo contiene firma XML."""
    alta_u = build_registro_alta_unsigned(
        factura={
            "num_factura": "F-2026-099",
            "fecha_emision": "2026-05-01",
            "base_imponible": 50.0,
            "cuota_iva": 10.5,
            "total_factura": 60.5,
            "tipo_factura": "F1",
            "nif_emisor": "B87654321",
        },
        empresa={"nif": "B87654321", "nombre_comercial": "Emp Mock"},
        cliente={"nif": "B00000000", "nombre": "Destinatario"},
        fingerprint="ee" * 32,
        registro_anterior=None,
        rectificada=None,
    )
    cert_pem, key_pem = _certificado_y_clave_pem()
    alta_xml = etree.tostring(alta_u, xml_declaration=True, encoding="utf-8")
    signed = sign_xml_xades(alta_xml, cert_pem, key_pem, None)
    inner = inner_xml_fragment_from_signed_registro_alta(
        empresa={"nif": "B87654321", "nombre_comercial": "Emp Mock"},
        factura={"nif_emisor": "B87654321"},
        signed_registro_alta_xml=signed,
    )
    soap = envolver_soap12(inner)

    def aeat_handler(request: httpx.Request) -> httpx.Response:
        body = request.content
        assert b"soap12:Envelope" in body or b"Envelope" in body
        assert b"Signature" in body
        resp_xml = """<?xml version="1.0" encoding="UTF-8"?>
<RespuestaSuministro xmlns="urn:aeat:test">
  <EstadoRegistro>Correcto</EstadoRegistro>
  <CSV>MOCK-CSV-VERIFACTU-TEST</CSV>
</RespuestaSuministro>"""
        return httpx.Response(200, text=resp_xml)

    transport = httpx.MockTransport(aeat_handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://aeat-mock.invalid") as client:
        r = await client.post(
            "/registro",
            content=soap.encode("utf-8"),
            headers={"Content-Type": 'application/soap+xml; charset=utf-8; action="RegistroFactura"'},
        )

    assert r.status_code == 200
    parsed = interpretar_respuesta_aeat(cuerpo=r.text, http_status=r.status_code)
    assert parsed.estado_factura_codigo == "aceptado"
    assert parsed.csv_aeat == "MOCK-CSV-VERIFACTU-TEST"
