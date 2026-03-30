"""
Firma digital XAdES-BES sobre XML (VeriFactu / remisión AEAT).

Se usa ``signxml.xades.XAdESSigner``, subclase de ``XMLSigner``, con el mismo perfil
criptográfico que XML-DSig envuelto (RSA-SHA256, SHA256) y los bloques XAdES exigidos
en el nivel BES (p. ej. ``SignedProperties``, ``SigningTime``, referencias al certificado).

Referencias: ETSI EN 319 132-1 (XAdES baseline), W3C XML Signature.
"""

from __future__ import annotations

from lxml import etree
from signxml import methods
from signxml.xades import XAdESSigner


def sign_xml_xades(
    xml_bytes: bytes,
    cert_pem: bytes,
    key_pem: bytes,
    password: bytes | None = None,
) -> bytes:
    """
    Firma el documento XML en modo **enveloped**: el nodo ``<ds:Signature>`` (y en XAdES
    el ``Object`` con ``QualifyingProperties``) se inserta bajo el elemento raíz.

    Parameters
    ----------
    xml_bytes:
        Documento UTF-8 (con o sin declaración XML).
    cert_pem:
        Certificado X.509 del firmante en PEM.
    key_pem:
        Clave privada en PEM (PKCS#8). Si está cifrada, pase ``password``.
    password:
        Contraseña en bytes para clave PEM cifrada (p. ej. ``b\"secret\"``).

    Returns
    -------
    bytes
        XML firmado con declaración ``<?xml version='1.0' encoding='utf-8'?>``.
    """
    parser = etree.XMLParser(resolve_entities=False)
    root = etree.fromstring(xml_bytes, parser=parser)

    signer = XAdESSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha256",
        digest_algorithm="sha256",
    )
    signed_root = signer.sign(
        root,
        key=key_pem,
        cert=cert_pem,
        passphrase=password,
    )
    return etree.tostring(
        signed_root,
        xml_declaration=True,
        encoding="utf-8",
    )
