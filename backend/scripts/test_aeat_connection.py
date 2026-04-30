#!/usr/bin/env python3
"""
Prueba de conectividad mTLS con AEAT VeriFactu sin enviar datos reales.

Valida:
- carga WSDL con zeep + ssl_context
- handshake TLS mutuo
- respuesta HTTP 200 o SOAP Fault manejable (sin timeout de conexión)
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from app.core.config import get_settings
from app.services.aeat_soap_client import AeatSoapClient

logger = logging.getLogger("aeat.handshake")


def _load_dotenv_like_app() -> None:
    root = Path(__file__).resolve().parents[1]
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    if (root / ".env").is_file():
        load_dotenv(dotenv_path=root / ".env")
    if (root.parent / ".env").is_file():
        load_dotenv(dotenv_path=root.parent / ".env")


def main() -> int:
    _load_dotenv_like_app()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    settings = get_settings()
    cert = (settings.AEAT_CLIENT_CERT_PATH or "").strip()
    key = (settings.AEAT_CLIENT_KEY_PATH or "").strip()
    wsdl = (
        (settings.AEAT_VERIFACTU_WSDL_URL or "").strip()
        or "https://www1.agenciatributaria.gob.es/wlpl/ICON-CONT/Sews/Facturacion/VeriFactu/V1/VeriFactu.wsdl"
    )
    endpoint = (settings.AEAT_VERIFACTU_SUBMIT_URL_TEST or "").strip()

    if not cert or not key:
        logger.error("Faltan AEAT_CLIENT_CERT_PATH o AEAT_CLIENT_KEY_PATH.")
        return 2
    if not endpoint:
        logger.error("Falta AEAT_VERIFACTU_SUBMIT_URL_TEST.")
        return 2

    logger.info("Iniciando handshake AEAT (sin envío real).")
    logger.info("WSDL: %s", wsdl)
    logger.info("Endpoint test: %s", endpoint)

    client = AeatSoapClient(cert_file=cert, key_file=key, settings=settings)
    try:
        result = client.test_connectivity(endpoint_url=endpoint)
    finally:
        client.close()

    print(
        json.dumps(
            {
                "ok": result.ok,
                "wsdl_url": result.wsdl_url,
                "endpoint": result.endpoint,
                "http_status": result.http_status,
                "detail": result.detail,
                "soap_fault": result.soap_fault,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if result.ok:
        logger.info("Prueba de conectividad AEAT completada OK.")
        return 0

    if "timeout" in result.detail.lower():
        logger.error("Handshake NO válido: timeout de conexión.")
        return 3

    logger.error("Handshake NO válido: %s", result.detail)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
