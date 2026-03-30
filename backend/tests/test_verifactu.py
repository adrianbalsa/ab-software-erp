"""
Flujo fiscal VeriFactu: firma XAdES-BES (signxml) + respuesta AEAT simulada sin red.

Valida que el XML de registro se firma correctamente y que el pipeline HTTP
(httpx.MockTransport) entrega una respuesta tipo AEAT que ``interpretar_respuesta_aeat``
clasifica sin contactar con Hacienda.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.core.xades_signer import sign_xml_xades
from app.services.verifactu_sender import (
    envolver_soap12,
    generar_xml_registro_facturacion_alta,
    interpretar_respuesta_aeat,
)


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
    xml_str = generar_xml_registro_facturacion_alta(
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
        hash_registro="aa" * 32,
        fingerprint="bb" * 32,
        prev_fingerprint="cc" * 32,
    )
    cert_pem, key_pem = _certificado_y_clave_pem()
    signed = sign_xml_xades(xml_str.encode("utf-8"), cert_pem, key_pem, None)
    assert b"ds:Signature" in signed or b"Signature" in signed
    assert b"http://uri.etsi.org/01903/v1.3.2#" in signed


@pytest.mark.asyncio
async def test_soap_firmado_post_mock_aeat_sin_red_interpreta_aceptado() -> None:
    """Simula POST SOAP tras firma; el handler valida que el cuerpo contiene firma XML."""
    xml_str = generar_xml_registro_facturacion_alta(
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
        hash_registro="ff" * 32,
        fingerprint="ee" * 32,
        prev_fingerprint=None,
    )
    cert_pem, key_pem = _certificado_y_clave_pem()
    signed = sign_xml_xades(xml_str.encode("utf-8"), cert_pem, key_pem, None)
    inner = re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", signed.decode("utf-8"), count=1)
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
