"""
Cliente SOAP AEAT VeriFactu basado en Zeep + WSDL oficial, con mTLS (``requests``).

- Envío: cuerpo SOAP 1.2 ya construido (firma XAdES embebida en el XML interno).
- Respuesta: deserialización estricta con los tipos del WSDL contra el nodo
  ``RespuestaRegFactuSistemaFacturacion`` (sin heurísticas DOM genéricas).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from xml.etree.ElementTree import ParseError as XmlStdParseError

import requests
import xmlschema
from lxml import etree
from zeep import Client
from zeep.exceptions import Fault, TransportError
from zeep.settings import Settings as ZeepSettings
from zeep.transports import Transport

from app.core.config import Settings as AppSettings
from app.services.aeat_client_py.exceptions import VeriFactuException
from app.services.aeat_client_py.xsd_validate import assert_well_formed_xml
from app.services.aeat_client_py.xsd_validate import validate_reg_factu_payload_against_suministro_lr_xsd

logger = logging.getLogger(__name__)

_NS_RESPUESTA: Final = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/"
    "es/aeat/tike/cont/ws/RespuestaSuministro.xsd"
)

@dataclass(frozen=True, slots=True)
class RegFactuPostResult:
    http_status: int
    raw_body: str
    respuesta: dict[str, Any] | None
    soap_fault: dict[str, Any] | None


def default_aeat_verifactu_wsdl_url() -> str:
    return (
        "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/"
        "aplicaciones/es/aeat/tike/cont/ws/SistemaFacturacion.wsdl"
    )


def default_aeat_suministro_lr_xsd_url() -> str:
    """Esquema ``SuministroLR.xsd`` empaquetado con la aplicación (importa ``SuministroInformacion.xsd`` local)."""
    return str(Path(__file__).resolve().parent / "xsd" / "SuministroLR.xsd")


def _zeep_settings() -> ZeepSettings:
    # El WSDL importa el esquema xmldsig vía entidades; hay que relajar forbid_entities.
    return ZeepSettings(
        strict=True,
        forbid_entities=False,
        forbid_external=False,
        xml_huge_tree=True,
    )


class AEATZeepClient:
    """
    Carga el WSDL oficial AEAT (tipos + binding document/literal) y usa la misma
    sesión TLS mutua que el certificado de empresa para el POST SOAP.
    """

    def __init__(
        self,
        *,
        wsdl_url: str,
        cert_file: str,
        key_file: str,
        app_settings: AppSettings,
    ) -> None:
        self._wsdl_url = wsdl_url.strip()
        self._cert_file = cert_file
        self._key_file = key_file
        self._app_settings = app_settings
        self._session = requests.Session()
        self._session.cert = (cert_file, key_file)
        self._session.verify = True
        transport = Transport(session=self._session, timeout=120, operation_timeout=120)
        self._client = Client(
            self._wsdl_url,
            transport=transport,
            settings=_zeep_settings(),
        )
        self._respuesta_elem = self._client.get_element(
            "{" + _NS_RESPUESTA + "}RespuestaRegFactuSistemaFacturacion"
        )

    def close(self) -> None:
        self._session.close()

    def _validate_request_payload_if_configured(self, signed_inner_xml_without_decl: str) -> None:
        if not self._app_settings.AEAT_VERIFACTU_XSD_VALIDATE_REQUEST:
            return
        xsd_url = (
            self._app_settings.AEAT_VERIFACTU_SUMINISTRO_LR_XSD_URL
            or default_aeat_suministro_lr_xsd_url()
        )
        try:
            validate_reg_factu_payload_against_suministro_lr_xsd(
                reg_factu_inner_xml=signed_inner_xml_without_decl,
                schema_location=xsd_url.strip(),
            )
        except (
            xmlschema.XMLSchemaException,
            ValueError,
            etree.XMLSyntaxError,
            OSError,
        ) as exc:
            raise VeriFactuException(
                f"Validación XSD (petición) contra SuministroLR: {exc}",
                code="XSD_REQUEST",
                detail=exc,
            ) from exc
        except Exception as exc:
            logger.exception(
                "Validación XSD SuministroLR: error no clasificado (petición VeriFactu)"
            )
            raise VeriFactuException(
                f"Validación XSD (petición) contra SuministroLR: {exc}",
                code="XSD_REQUEST",
                detail=exc,
            ) from exc

    def _validate_soap_envelope_well_formed(self, soap_body: str) -> None:
        raw = soap_body.encode("utf-8")
        try:
            assert_well_formed_xml(raw)
        except XmlStdParseError as exc:
            raise VeriFactuException(
                f"SOAP no es XML bien formado: {exc}",
                code="SOAP_MALFORMED",
                detail=exc,
            ) from exc
        except etree.XMLSyntaxError as exc:
            raise VeriFactuException(
                f"SOAP no es XML bien formado: {exc}",
                code="SOAP_MALFORMED",
                detail=exc,
            ) from exc
        except Exception as exc:
            logger.exception("SOAP: assert_well_formed falló con error no clasificado")
            raise VeriFactuException(
                f"SOAP no es XML bien formado: {exc}",
                code="SOAP_MALFORMED",
                detail=exc,
            ) from exc

    def post_registro_facturacion(
        self,
        *,
        service_url: str,
        soap12_body: str,
        signed_inner_xml_for_optional_xsd: str,
    ) -> RegFactuPostResult:
        """
        POST del sobre SOAP 1.2 completo (``soap12:Envelope``).

        ``signed_inner_xml_for_optional_xsd`` es el fragmento envuelto por
        ``RegFactuSistemaFacturacion`` (sin declaración XML), el mismo que se pasa
        a ``envolver_soap12``; sirve para validación XSD opcional previa al envío.
        """
        self._validate_soap_envelope_well_formed(soap12_body)
        self._validate_request_payload_if_configured(signed_inner_xml_for_optional_xsd)

        url = service_url.strip()
        headers = {
            "Content-Type": 'application/soap+xml; charset=utf-8; action="RegistroFactura"',
            "Accept": "application/soap+xml, text/xml",
        }
        try:
            resp = self._session.post(
                url,
                data=soap12_body.encode("utf-8"),
                headers=headers,
                timeout=120,
            )
        except requests.exceptions.RequestException as exc:
            raise VeriFactuException(
                f"Error de red petición AEAT (requests): {exc}",
                code="AEAT_TRANSPORT",
                detail=exc,
            ) from exc

        text = resp.text or ""
        status = int(resp.status_code)

        fault = self._parse_soap_fault(text.encode("utf-8"))
        if fault is not None:
            return RegFactuPostResult(
                http_status=status,
                raw_body=text,
                respuesta=None,
                soap_fault=fault,
            )

        parsed = self._parse_respuesta_body(text.encode("utf-8"))
        return RegFactuPostResult(
            http_status=status,
            raw_body=text,
            respuesta=parsed,
            soap_fault=None,
        )

    def _parse_respuesta_body(self, content: bytes) -> dict[str, Any] | None:
        if not content.strip():
            return None
        doc = etree.fromstring(content)
        body_el = self._find_soap_body(doc)
        if body_el is None:
            return None
        for child in body_el:
            tag = etree.QName(child.tag).localname
            if tag == "Fault":
                return None
            if tag == "RespuestaRegFactuSistemaFacturacion":
                try:
                    return self._respuesta_elem.parse(child, self._client.wsdl.types)
                except (TypeError, LookupError, AttributeError, KeyError, ValueError) as exc:
                    logger.warning(
                        "Zeep no pudo parsear RespuestaRegFactuSistemaFacturacion (tipado): %s",
                        exc,
                    )
                    return None
                except Exception as exc:
                    logger.exception(
                        "Zeep: fallo inesperado parseando RespuestaRegFactuSistemaFacturacion"
                    )
                    return None
        return None

    @staticmethod
    def _find_soap_body(doc: etree._Element) -> etree._Element | None:
        soap12 = "http://www.w3.org/2003/05/soap-envelope"
        soap11 = "http://schemas.xmlsoap.org/soap/envelope/"
        for ns in (soap12, soap11):
            el = doc.find(f"{{{ns}}}Body")
            if el is not None:
                return el
        return None

    @staticmethod
    def _parse_soap_fault(content: bytes) -> dict[str, Any] | None:
        if not content.strip():
            return None
        try:
            doc = etree.fromstring(content)
        except etree.XMLSyntaxError:
            return None
        body_el = AEATZeepClient._find_soap_body(doc)
        if body_el is None:
            return None
        fault_el = None
        for child in body_el:
            if etree.QName(child.tag).localname == "Fault":
                fault_el = child
                break
        if fault_el is None:
            return None

        soap11 = "http://schemas.xmlsoap.org/soap/envelope/"
        # SOAP 1.1 típico
        fc = fault_el.findtext(f"{{{soap11}}}faultcode")
        fs = fault_el.findtext(f"{{{soap11}}}faultstring")
        if fc is None and fs is None:
            fc = fault_el.findtext("faultcode")
            fs = fault_el.findtext("faultstring")
        if fc or fs:
            return {
                "faultcode": (fc or "").strip() or None,
                "faultstring": (fs or "").strip() or None,
            }

        # SOAP 1.2
        reason_txt: str | None = None
        code_txt: str | None = None
        for sub in fault_el:
            ln = etree.QName(sub.tag).localname
            if ln == "Reason":
                for t in sub.iter():
                    if etree.QName(t.tag).localname == "Text" and t.text:
                        reason_txt = (t.text or "").strip()
                        break
            if ln == "Code":
                for t in sub.iter():
                    if etree.QName(t.tag).localname == "Value" and t.text:
                        code_txt = (t.text or "").strip()
                        break
        full = (reason_txt or "".join(fault_el.itertext())).strip()
        return {
            "faultcode": code_txt,
            "faultstring": full[:2000] or None,
        }


def zeep_transport_error_to_verifactu_exc(exc: TransportError) -> VeriFactuException:
    return VeriFactuException(
        str(exc),
        code="AEAT_TRANSPORT",
        http_status=getattr(exc, "status_code", None),
        detail=exc,
    )


def fault_to_verifactu_exc(exc: Fault) -> VeriFactuException:
    return VeriFactuException(
        str(exc.message) if getattr(exc, "message", None) else repr(exc),
        code="SOAP_FAULT",
        fault_code=getattr(exc, "code", None),
        fault_string=getattr(exc, "message", None) or str(exc),
        detail=exc,
    )


def map_verifactu_exc(exc: Exception) -> VeriFactuException:
    if isinstance(exc, VeriFactuException):
        return exc
    if isinstance(exc, Fault):
        return fault_to_verifactu_exc(exc)
    if isinstance(exc, TransportError):
        return zeep_transport_error_to_verifactu_exc(exc)
    return VeriFactuException(str(exc), code="AEAT_UNKNOWN", detail=exc)
