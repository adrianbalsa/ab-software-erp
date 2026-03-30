"""Firma XAdES-BES (signxml) sobre XML de registro mínimo."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.core.xades_signer import sign_xml_xades


def _certificado_y_clave_pem() -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-xades-verifactu")])
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


def test_sign_xml_xades_enveloped_ds_y_xades() -> None:
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<RegistroFacturacionAltaVeriFactu versionFormato="1.0">'
        b"<Cabecera><IdVersion>1.0</IdVersion></Cabecera>"
        b"</RegistroFacturacionAltaVeriFactu>"
    )
    cert_pem, key_pem = _certificado_y_clave_pem()
    out = sign_xml_xades(xml, cert_pem, key_pem, None)
    assert b'xmlns:ds="http://www.w3.org/2000/09/xmldsig#' in out
    assert b"http://uri.etsi.org/01903/v1.3.2#" in out
    assert b"<ds:Signature" in out
