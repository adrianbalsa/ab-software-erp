from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree
from signxml import SignatureConfiguration, XMLVerifier

from app.services.crypto_service import sign_invoice_xml
from app.services.verifactu_xml_service import VeriFactuXmlService


def _build_test_p12(password: bytes) -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "verifactu-sign-test")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    p12_bytes = pkcs12.serialize_key_and_certificates(
        name=b"verifactu-sign-test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    return p12_bytes, cert_pem


def test_verifactu_xml_is_well_formed_and_xades_signature_verifies() -> None:
    service = VeriFactuXmlService()
    xml_unsigned = service.build_invoice_xml(
        factura={
            "num_factura": "VF-2026-0001",
            "numero_factura": "VF-2026-0001",
            "fecha_emision": "2026-04-23",
            "nif_emisor": "B12345678",
            "base_imponible": "100.00",
            "cuota_iva": "21.00",
            "total_factura": "121.00",
            "tipo_factura": "F1",
            "desglose_por_tipo": [
                {"tipo_iva_porcentaje": "21.00", "base_imponible": "100.00", "cuota_iva": "21.00"}
            ],
        },
        empresa={"nif": "B12345678", "nombre_comercial": "AB Logistics Test"},
        cliente={"nif": "A11111111", "nombre": "Cliente QA"},
        previous_fingerprint="c" * 64,
        previous_invoice={
            "nif_emisor": "B12345678",
            "num_factura": "VF-2026-0000",
            "fecha_emision": "2026-04-22",
        },
    )
    service.validate_against_regfactu_schema(xml_unsigned)

    p12_password = b"test-password"
    p12_bytes, cert_pem = _build_test_p12(p12_password)
    signed_xml = sign_invoice_xml(xml_unsigned, p12_bytes, p12_password)

    root = etree.fromstring(signed_xml.encode("utf-8"))
    ns = {
        "ds": "http://www.w3.org/2000/09/xmldsig#",
        "xades": "http://uri.etsi.org/01903/v1.3.2#",
    }
    assert root.find(".//xades:SignedProperties", namespaces=ns) is not None
    assert root.find(".//ds:SignatureValue", namespaces=ns) is not None
    assert root.find(".//ds:KeyInfo", namespaces=ns) is not None

    XMLVerifier().verify(
        signed_xml.encode("utf-8"),
        x509_cert=cert_pem,
        expect_config=SignatureConfiguration(expect_references=3),
    )
