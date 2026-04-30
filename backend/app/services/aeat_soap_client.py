from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import logging
import ssl
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from zeep import Client
from zeep.transports import Transport

from app.core.config import Settings
from app.services.aeat_client_py import AEATZeepClient, RegFactuPostResult, default_aeat_verifactu_wsdl_url

logger = logging.getLogger(__name__)


class _SSLContextAdapter(HTTPAdapter):
    """HTTPAdapter para inyectar ssl_context explícito en requests/urllib3."""

    def __init__(self, ssl_context: ssl.SSLContext, *args: Any, **kwargs: Any) -> None:
        self._ssl_context = ssl_context
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        kwargs["ssl_context"] = self._ssl_context
        return super().init_poolmanager(*args, **kwargs)


@dataclass(frozen=True, slots=True)
class AeatHandshakeResult:
    ok: bool
    wsdl_url: str
    endpoint: str
    http_status: int | None
    detail: str
    soap_fault: dict[str, Any] | None


class AeatSubmissionStatus(StrEnum):
    ACCEPTED = "accepted"
    ACCEPTED_WITH_ERRORS = "accepted_with_errors"
    REJECTED = "rejected"
    TECHNICAL_ERROR = "technical_error"


@dataclass(frozen=True, slots=True)
class AeatSoapResult:
    status: AeatSubmissionStatus
    status_code: str
    http_status: int | None
    csv: str | None
    error_code: str | None
    error_description: str | None
    response_snippet: str | None
    post_result: RegFactuPostResult


class AeatSoapClient:
    """
    Cliente SOAP 1.2 para AEAT VeriFactu con Zeep + mTLS.

    El **CSV / huella** del registro facturación proviene del XML interior firmado, generado en
    aplicación con la misma cadena canónica que
    :class:`app.core.verifactu_hashing.CanonicalHashService` (emisión / ``hash_registro``).
    Este módulo no recalcula hashes: solo transporta el sobre SOAP; la acción SOAP 1.2 coincide
    con :data:`app.services.aeat_client_py.zeep_client.AEAT_VERIFACTU_SOAP_ACTION`.
    """

    def __init__(
        self,
        *,
        cert_file: str,
        key_file: str,
        settings: Settings,
    ) -> None:
        wsdl_url = (settings.AEAT_VERIFACTU_WSDL_URL or "").strip() or default_aeat_verifactu_wsdl_url()
        self._settings = settings
        self._wsdl_url = wsdl_url
        self._cert_file = cert_file
        self._key_file = key_file
        self._client = AEATZeepClient(
            wsdl_url=wsdl_url,
            cert_file=cert_file,
            key_file=key_file,
            app_settings=settings,
        )
        self._session = self._build_mtls_session(cert_file=cert_file, key_file=key_file)
        self._zeep_transport = Transport(session=self._session, timeout=30, operation_timeout=30)
        self._zeep_client = Client(self._wsdl_url, transport=self._zeep_transport)

    def close(self) -> None:
        self._client.close()
        self._session.close()

    @staticmethod
    def _build_mtls_session(*, cert_file: str, key_file: str) -> requests.Session:
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.load_cert_chain(certfile=cert_file, keyfile=key_file)

        retries = Retry(
            total=2,
            connect=2,
            read=0,
            status=0,
            backoff_factor=0.3,
            allowed_methods=frozenset({"GET", "POST"}),
        )
        adapter = _SSLContextAdapter(ssl_context=ssl_context, max_retries=retries)
        session = requests.Session()
        session.cert = (cert_file, key_file)
        session.verify = True
        session.mount("https://", adapter)
        return session

    def test_connectivity(self, *, endpoint_url: str | None = None) -> AeatHandshakeResult:
        """
        Verifica conectividad mTLS contra AEAT sin enviar datos reales.

        Estrategia:
        1) cargar WSDL con zeep + Transport (ssl_context)
        2) enviar SOAP mínimo intencionadamente inválido al endpoint para recibir SOAP Fault manejable
        """
        target = (
            (endpoint_url or "").strip()
            or (self._settings.AEAT_VERIFACTU_SUBMIT_URL_TEST or "").strip()
        )
        if not target:
            return AeatHandshakeResult(
                ok=False,
                wsdl_url=self._wsdl_url,
                endpoint="",
                http_status=None,
                detail="Falta AEAT_VERIFACTU_SUBMIT_URL_TEST para la prueba de conectividad.",
                soap_fault=None,
            )

        try:
            operations = [
                op_name
                for service in self._zeep_client.wsdl.services.values()
                for port in service.ports.values()
                for op_name in port.binding._operations.keys()
            ]
            logger.info("AEAT WSDL cargado con %s operaciones detectadas.", len(operations))
        except Exception:  # noqa: BLE001
            logger.exception("Error cargando WSDL AEAT con zeep/ssl_context.")
            return AeatHandshakeResult(
                ok=False,
                wsdl_url=self._wsdl_url,
                endpoint=target,
                http_status=None,
                detail="Fallo cargando WSDL con mTLS (revisar certificado, cadena FNMT y TLS).",
                soap_fault=None,
            )

        invalid_probe = """<?xml version="1.0" encoding="UTF-8"?>
<soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <vf:Consulta xmlns:vf="https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/ws/Consulta.wsdl">
      <vf:Ping>handshake</vf:Ping>
    </vf:Consulta>
  </soap12:Body>
</soap12:Envelope>"""
        try:
            response = self._session.post(
                target,
                data=invalid_probe.encode("utf-8"),
                headers={
                    "Content-Type": 'application/soap+xml; charset=utf-8; action="Consulta"',
                    "Accept": "application/soap+xml, text/xml",
                },
                timeout=30,
            )
            body = response.text or ""
            fault = self._client._parse_soap_fault(body.encode("utf-8"))  # noqa: SLF001
            if response.status_code == 200:
                return AeatHandshakeResult(
                    ok=True,
                    wsdl_url=self._wsdl_url,
                    endpoint=target,
                    http_status=200,
                    detail="Handshake mTLS OK (HTTP 200).",
                    soap_fault=fault,
                )
            if fault is not None:
                return AeatHandshakeResult(
                    ok=True,
                    wsdl_url=self._wsdl_url,
                    endpoint=target,
                    http_status=response.status_code,
                    detail="Handshake mTLS establecido; AEAT respondió con SOAP Fault controlado.",
                    soap_fault=fault,
                )
            return AeatHandshakeResult(
                ok=False,
                wsdl_url=self._wsdl_url,
                endpoint=target,
                http_status=response.status_code,
                detail="Respuesta no timeout pero tampoco SOAP fault reconocible.",
                soap_fault=None,
            )
        except requests.exceptions.SSLError as exc:
            logger.exception("SSL handshake con AEAT falló (posible cadena FNMT o cert/key).")
            return AeatHandshakeResult(
                ok=False,
                wsdl_url=self._wsdl_url,
                endpoint=target,
                http_status=None,
                detail=f"SSL handshake error: {exc}",
                soap_fault=None,
            )
        except requests.exceptions.Timeout as exc:
            logger.exception("Timeout conectando con AEAT VeriFactu.")
            return AeatHandshakeResult(
                ok=False,
                wsdl_url=self._wsdl_url,
                endpoint=target,
                http_status=None,
                detail=f"Connection timeout: {exc}",
                soap_fault=None,
            )
        except requests.exceptions.RequestException as exc:
            logger.exception("Error de transporte en prueba de conectividad AEAT.")
            return AeatHandshakeResult(
                ok=False,
                wsdl_url=self._wsdl_url,
                endpoint=target,
                http_status=None,
                detail=f"Error de transporte: {exc}",
                soap_fault=None,
            )

    def submit_signed_soap(
        self,
        *,
        service_url: str,
        soap12_body: str,
        signed_inner_xml: str,
    ) -> AeatSoapResult:
        """
        Envía XML firmado a endpoint AEAT pruebas/producción y mapea estados:
        aceptado, rechazado y aceptado con errores.
        """
        post_result = self._client.post_registro_facturacion(
            service_url=service_url,
            soap12_body=soap12_body,
            signed_inner_xml_for_optional_xsd=signed_inner_xml,
        )
        status = AeatSubmissionStatus.TECHNICAL_ERROR
        status_code = "error_tecnico"
        if post_result.soap_fault is not None:
            status = AeatSubmissionStatus.REJECTED
            status_code = "rechazado"
        elif post_result.respuesta is not None:
            rows = post_result.respuesta.get("RespuestaLinea") or []
            row0 = rows[0] if isinstance(rows, list) and rows else {}
            estado_registro = str((row0 or {}).get("EstadoRegistro") or "").strip().lower()
            if estado_registro == "correcto":
                status = AeatSubmissionStatus.ACCEPTED
                status_code = "aceptado"
            elif estado_registro in {"aceptadoconerrores", "aceptado_con_errores"}:
                status = AeatSubmissionStatus.ACCEPTED_WITH_ERRORS
                status_code = "aceptado_con_errores"
            elif estado_registro:
                status = AeatSubmissionStatus.REJECTED
                status_code = "rechazado"

        csv = None
        error_code = None
        error_description = None
        if post_result.respuesta is not None:
            csv_raw = post_result.respuesta.get("CSV")
            csv = str(csv_raw).strip() if csv_raw else None
            rows = post_result.respuesta.get("RespuestaLinea") or []
            row0 = rows[0] if isinstance(rows, list) and rows else {}
            ec = (row0 or {}).get("CodigoErrorRegistro")
            ed = (row0 or {}).get("DescripcionErrorRegistro")
            error_code = str(ec).strip() if ec else None
            error_description = str(ed).strip() if ed else None
        elif post_result.soap_fault is not None:
            fc = post_result.soap_fault.get("faultcode")
            fs = post_result.soap_fault.get("faultstring")
            error_code = str(fc).strip() if fc else None
            error_description = str(fs).strip() if fs else None

        return AeatSoapResult(
            status=status,
            status_code=status_code,
            http_status=post_result.http_status,
            csv=csv,
            error_code=error_code,
            error_description=error_description,
            response_snippet=(post_result.raw_body[:8000] if post_result.raw_body else None),
            post_result=post_result,
        )
