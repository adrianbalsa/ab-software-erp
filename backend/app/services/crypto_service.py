from __future__ import annotations

from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree
from lxml.etree import XMLSyntaxError
from signxml import methods
from signxml.xades import XAdESSigner


def _read_p12_content(certificate_p12: bytes | bytearray | str) -> bytes:
    if isinstance(certificate_p12, (bytes, bytearray)):
        return bytes(certificate_p12)
    with open(certificate_p12, "rb") as fh:
        return fh.read()


def sign_invoice_xml(
    xml_content: str | bytes,
    certificate_p12: bytes | bytearray | str,
    password: str | bytes | None,
) -> str:
    """
    Firma XML con perfil XAdES-BES (enveloped) para flujo VeriFactu.

    El resultado incluye ``SignedProperties``, ``SignatureValue`` y ``KeyInfo``.
    """
    xml_bytes = xml_content.encode("utf-8") if isinstance(xml_content, str) else xml_content
    p12_bytes = _read_p12_content(certificate_p12)
    pwd_bytes = password.encode("utf-8") if isinstance(password, str) else password

    private_key, certificate, _chain = pkcs12.load_key_and_certificates(p12_bytes, pwd_bytes)
    if private_key is None or certificate is None:
        raise ValueError("PKCS#12 inválido: falta clave privada o certificado.")

    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)

    parser = etree.XMLParser(resolve_entities=False)
    signer = XAdESSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha256",
        digest_algorithm="sha256",
    )
    try:
        root = etree.fromstring(xml_bytes, parser=parser)
        signed = signer.sign(root, key=key_pem, cert=cert_pem, passphrase=None)
        signed_xml = etree.tostring(signed, encoding="utf-8", xml_declaration=True).decode("utf-8")
    except XMLSyntaxError:
        # Fragmento RegFactu con múltiples nodos raíz (Cabecera + RegistroFactura).
        raw = xml_bytes.decode("utf-8").strip()
        if raw.startswith("<?xml"):
            raw = raw.split("?>", 1)[1].strip()
        wrapped = etree.fromstring(
            (
                '<sf:RegFactuSistemaFacturacion '
                'xmlns:sf="https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroLR.xsd">'
                f"{raw}"
                "</sf:RegFactuSistemaFacturacion>"
            ).encode("utf-8"),
            parser=parser,
        )
        signed_wrapped = signer.sign(wrapped, key=key_pem, cert=cert_pem, passphrase=None)
        signed_xml = etree.tostring(signed_wrapped, encoding="utf-8", xml_declaration=True).decode("utf-8")

    ns = {
        "ds": "http://www.w3.org/2000/09/xmldsig#",
        "xades": "http://uri.etsi.org/01903/v1.3.2#",
    }
    required_paths: dict[str, str] = {
        "SignedProperties": ".//xades:SignedProperties",
        "SignatureValue": ".//ds:SignatureValue",
        "KeyInfo": ".//ds:KeyInfo",
    }
    try:
        signed_tree = etree.fromstring(signed_xml.encode("utf-8"), parser=parser)
    except XMLSyntaxError:
        fragment = signed_xml.strip()
        if fragment.startswith("<?xml"):
            fragment = fragment.split("?>", 1)[1].strip()
        signed_tree = etree.fromstring(f"<SignedRoot>{fragment}</SignedRoot>".encode("utf-8"), parser=parser)
    for required, xpath in required_paths.items():
        if signed_tree.find(xpath, namespaces=ns) is None:
            raise ValueError(f"Firma XAdES incompleta: falta nodo requerido {required}.")

    return signed_xml
