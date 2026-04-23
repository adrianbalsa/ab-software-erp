from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.config import Settings
from app.services.aeat_client_py import AEATZeepClient, RegFactuPostResult, default_aeat_verifactu_wsdl_url


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
        self._client = AEATZeepClient(
            wsdl_url=wsdl_url,
            cert_file=cert_file,
            key_file=key_file,
            app_settings=settings,
        )

    def close(self) -> None:
        self._client.close()

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
