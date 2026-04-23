"""
Generación de XML de registro de facturación (VeriFactu / SIF 1.0, estructura lógica),
**firma XAdES-BES** del fragmento de registro y envío HTTP(S) con autenticación mutua
(mTLS) hacia endpoints configurables (pruebas / producción).

Flujo: ``Cabecera`` + ``RegistroFactura``/``RegistroAlta`` (**SuministroLR.xsd**) → firma
XAdES-BES enveloped del nodo ``RegistroAlta`` → composición del fragmento interior →
validación XSD opcional → envoltorio SOAP 1.2 (``RegFactuSistemaFacturacion``) → POST.
El certificado de cliente TLS y el de firma XML deben ser el mismo par (o al menos el
admitido por la AEAT para el NIF/empresa).

Certificados (dónde los subirá el titular del tenant en el futuro):
- **Recomendado en producción**: almacenar el .p12 o pares .pem cifrados por aplicación
  (KMS, Vault o cifrado en reposo con clave de empresa) y referenciarlos por
  ``empresa.aeat_client_p12_path`` / ``aeat_client_cert_path`` + ``aeat_client_key_path``
  tras un flujo seguro de subida en dashboard (solo rol admin), nunca en el repo.
- **Desarrollo / fallback**: variables ``AEAT_CLIENT_P12_PATH`` + ``AEAT_CLIENT_P12_PASSWORD``
  o ``AEAT_CLIENT_CERT_PATH`` + ``AEAT_CLIENT_KEY_PATH`` (+ ``AEAT_CLIENT_KEY_PASSWORD`` si la
  clave PEM está cifrada).

Sin ``AEAT_VERIFACTU_ENABLED=true`` o sin URL/certificado, no se realiza llamada HTTP.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, cast
from xml.etree import ElementTree as ET

import httpx
import requests
from lxml import etree
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from app.core.config import Settings
from app.core.config import get_settings
from app.core.crypto import pii_crypto
from app.core.xades_signer import sign_xml_xades
from app.services.crypto_service import sign_invoice_xml
from app.services.suministro_lr_xml import FacturaRectificadaRefAEAT
from app.services.suministro_lr_xml import RegistroAnteriorAEAT
from app.services.suministro_lr_xml import fecha_iso_u_otra_a_dd_mm_yyyy
from app.services.suministro_lr_xml import inner_xml_fragment_from_signed_registro_alta
from app.services.suministro_lr_xml import inner_xml_fragment_unsigned_alta_for_tests
from app.services.suministro_lr_xml import build_registro_alta_unsigned
from app.services.aeat_client_py import RegFactuPostResult
from app.services.aeat_client_py import VeriFactuException
from app.services.aeat_soap_client import AeatSoapClient
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.db.supabase import get_supabase
from app.models.webhook import WebhookEventType
from app.services.webhook_service import run_webhook_deliveries_for_event

logger = logging.getLogger(__name__)


def _classify_transport_detail(detail: Any) -> str:
    """
    Clasifica el detalle envuelto en VeriFactuException(code=AEAT_TRANSPORT).
    Cubre ``requests`` (uso actual) y ``httpx`` por si el transporte cambia.
    """
    if detail is None:
        return "other"
    if isinstance(
        detail,
        (
            requests.exceptions.Timeout,
            requests.exceptions.ReadTimeout,
        ),
    ):
        return "timeout"
    if isinstance(
        detail,
        (
            requests.exceptions.ConnectionError,
            requests.exceptions.ConnectTimeout,
        ),
    ):
        return "connect"
    # httpx (transporte alternativo / dependencias transitivas)
    if isinstance(
        detail,
        (
            httpx.TimeoutException,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
        ),
    ):
        return "timeout"
    if isinstance(
        detail,
        (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ProxyError,
        ),
    ):
        return "connect"
    return "other"


_NS_SOAP12 = "http://www.w3.org/2003/05/soap-envelope"
_NS_SF_DEFAULT = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/"
    "es/aeat/tike/cont/ws/SuministroLR.xsd"
)
_NS_SJE_DEFAULT = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/"
    "es/aeat/tike/cont/ws/SuministroInformacion.xsd"
)


def generar_xml_registro_facturacion_alta(
    *,
    factura: Mapping[str, Any],
    empresa: Mapping[str, Any],
    cliente: Mapping[str, Any],
    hash_registro: str,
    fingerprint: str,
    prev_fingerprint: str | None,
    registro_anterior: RegistroAnteriorAEAT | None = None,
    rectificada: FacturaRectificadaRefAEAT | None = None,
) -> str:
    """
    Fragmento interior del sobre AEAT (hijo de ``RegFactuSistemaFacturacion``): ``Cabecera`` +
    ``RegistroFactura`` → ``RegistroAlta`` según **SuministroLR.xsd** / SuministroInformacion.

    ``hash_registro`` se conserva en la firma de la función por compatibilidad con llamadas
    existentes; el XSD oficial no incluye ese campo en ``RegistroAlta``.
    """
    _ = hash_registro
    pfp = str(prev_fingerprint or "").strip()
    if pfp and registro_anterior is None:
        raise ValueError(
            "Encadenamiento AEAT: con prev_fingerprint debe proporcionarse registro_anterior "
            "(datos de la factura previa)."
        )
    if (not pfp) and registro_anterior is not None:
        raise ValueError("registro_anterior no debe informarse sin prev_fingerprint.")
    inner = inner_xml_fragment_unsigned_alta_for_tests(
        factura=factura,
        empresa=empresa,
        cliente=cliente,
        fingerprint=str(fingerprint).strip(),
        registro_anterior=registro_anterior,
        rectificada=rectificada,
    )
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + inner


async def _obtener_registro_anterior_aeat(
    db: SupabaseAsync,
    *,
    empresa_id: str,
    prev_fingerprint: str | None,
) -> RegistroAnteriorAEAT | None:
    pfp = str(prev_fingerprint or "").strip()
    if not pfp:
        return None
    res: Any = await db.execute(
        db.table("facturas")
        .select("nif_emisor, num_factura, fecha_emision")
        .eq("empresa_id", empresa_id)
        .eq("fingerprint", pfp)
        .limit(1)
    )
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    if not rows:
        raise ValueError(
            "AEAT encadenamiento: no se halló la factura previa para el fingerprint de cadena."
        )
    row = rows[0]
    raw_nif = row.get("nif_emisor")
    nif_plain = raw_nif
    if isinstance(raw_nif, str) and raw_nif.strip():
        nif_plain = pii_crypto.decrypt_pii(raw_nif) or raw_nif
    nif_s = str(nif_plain or "").strip()
    num = str(row.get("num_factura") or "").strip()
    fecha = fecha_iso_u_otra_a_dd_mm_yyyy(str(row.get("fecha_emision") or ""))
    return RegistroAnteriorAEAT(
        id_emisor_factura=nif_s,
        num_serie_factura=num or "SIN-NUM",
        fecha_expedicion=fecha,
        huella=pfp,
    )


async def _obtener_factura_rectificada_aeat(
    db: SupabaseAsync,
    *,
    empresa_id: str,
    factura: Mapping[str, Any],
) -> FacturaRectificadaRefAEAT | None:
    tipo = str(factura.get("tipo_factura") or "").strip().upper()
    if not tipo.startswith("R"):
        return None
    rect_id = factura.get("factura_rectificada_id")
    if rect_id is None:
        return None
    try:
        rid = int(rect_id)
    except (TypeError, ValueError):
        return None
    res: Any = await db.execute(
        db.table("facturas")
        .select("nif_emisor, num_factura, fecha_emision")
        .eq("empresa_id", empresa_id)
        .eq("id", rid)
        .limit(1)
    )
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    if not rows:
        raise ValueError(
            f"AEAT rectificativa: no existe la factura rectificada id={rid} para esta empresa."
        )
    row = rows[0]
    raw_nif = row.get("nif_emisor")
    nif_plain = raw_nif
    if isinstance(raw_nif, str) and raw_nif.strip():
        nif_plain = pii_crypto.decrypt_pii(raw_nif) or raw_nif
    nif_s = str(nif_plain or "").strip()
    num = str(row.get("num_factura") or "").strip()
    fecha = fecha_iso_u_otra_a_dd_mm_yyyy(str(row.get("fecha_emision") or ""))
    return FacturaRectificadaRefAEAT(
        id_emisor_factura=nif_s,
        num_serie_factura=num or "SIN-NUM",
        fecha_expedicion=fecha,
    )


def envolver_soap12(
    cuerpo_xml_sin_decl: str,
    *,
    ns_sf: str | None = None,
    ns_sje: str | None = None,
) -> str:
    """Envoltorio SOAP 1.2 con wrapper ``sf:RegFactuSistemaFacturacion``."""
    inner = cuerpo_xml_sin_decl.strip()
    if inner.startswith("<?xml"):
        inner = re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", inner, count=1)
    sf = (ns_sf or _NS_SF_DEFAULT).strip() or _NS_SF_DEFAULT
    sje = (ns_sje or _NS_SJE_DEFAULT).strip() or _NS_SJE_DEFAULT
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<soap12:Envelope xmlns:soap12="{_NS_SOAP12}" xmlns:sf="{sf}" xmlns:sje="{sje}">\n'
        "  <soap12:Body>\n"
        "    <sf:RegFactuSistemaFacturacion>\n"
        f"{inner}\n"
        "    </sf:RegFactuSistemaFacturacion>\n"
        "  </soap12:Body>\n"
        "</soap12:Envelope>\n"
    )


@dataclass(frozen=True, slots=True)
class AeatEnvioResultado:
    estado_envio_tabla: str
    estado_factura_codigo: str
    codigo_error: str | None
    descripcion_error: str | None
    csv_aeat: str | None
    http_status: int | None
    response_snippet: str | None


def interpretar_respuesta_zeeo(
    *,
    parsed: dict[str, Any],
    http_status: int | None,
    raw_body: str,
) -> AeatEnvioResultado:
    """
    Mapea ``RespuestaRegFactuSistemaFacturacion`` deserializada por Zeep (WSDL AEAT)
    al modelo interno de persistencia.
    """
    raw = (raw_body or "")[:24000]
    estado_envio = str(parsed.get("EstadoEnvio") or "").strip()
    csv_top = (parsed.get("CSV") or "").strip() or None
    lineas = parsed.get("RespuestaLinea") or []
    if not isinstance(lineas, list):
        lineas = []

    codes: list[str] = []
    descs: list[str] = []
    agg_estado: str | None = None

    for ln in lineas:
        if not isinstance(ln, dict):
            continue
        sr = str(ln.get("EstadoRegistro") or "").strip()
        if sr == "Incorrecto":
            agg_estado = "rechazado"
        elif sr == "AceptadoConErrores" and agg_estado != "rechazado":
            agg_estado = "aceptado_con_errores"
        c = ln.get("CodigoErrorRegistro")
        if c is not None and str(c).strip():
            if isinstance(c, (int, float)):
                codes.append(str(int(c)))
            else:
                codes.append(str(c).strip())
        d = ln.get("DescripcionErrorRegistro")
        if d is not None and str(d).strip():
            descs.append(str(d).strip())

    if agg_estado is None and lineas:
        if all(
            str((x or {}).get("EstadoRegistro") or "").strip() == "Correcto"
            for x in lineas
            if isinstance(x, dict)
        ):
            agg_estado = "aceptado"

    if agg_estado is None:
        if estado_envio == "Incorrecto":
            agg_estado = "rechazado"
        elif estado_envio == "ParcialmenteCorrecto":
            agg_estado = "aceptado_con_errores"
        elif estado_envio == "Correcto":
            agg_estado = "aceptado"
        else:
            agg_estado = "aceptado_con_errores"

    codigo_e = codes[0] if codes else None
    descr_e = " | ".join(descs) if descs else None

    estado_tabla = {
        "aceptado": "Aceptado",
        "aceptado_con_errores": "Aceptado con Errores",
        "rechazado": "Rechazado",
    }.get(agg_estado, "Aceptado con Errores")

    return AeatEnvioResultado(
        estado_envio_tabla=estado_tabla,
        estado_factura_codigo=agg_estado,
        codigo_error=codigo_e,
        descripcion_error=descr_e,
        csv_aeat=csv_top,
        http_status=http_status,
        response_snippet=raw[:8000],
    )


def interpretar_respuesta_soap_fault(
    *,
    fault: dict[str, Any],
    http_status: int | None,
    raw_body: str,
) -> AeatEnvioResultado:
    raw = (raw_body or "")[:24000]
    fs = str(fault.get("faultstring") or "").strip()
    fc = fault.get("faultcode")
    code = str(fc).strip() if fc is not None else None
    st = http_status or 0
    tech = st >= 500 or st == 0
    return AeatEnvioResultado(
        estado_envio_tabla="Error técnico" if tech else "Rechazado",
        estado_factura_codigo="error_tecnico" if tech else "rechazado",
        codigo_error=code or (str(st) if st else "SOAP_FAULT"),
        descripcion_error=fs or (raw[:2000] if raw else None),
        csv_aeat=None,
        http_status=http_status,
        response_snippet=raw[:8000],
    )


_CSV_RE = re.compile(r"CSV\s*[:=]\s*([A-Za-z0-9\-_/]+)", re.I)


def _extraer_csv(text: str) -> str | None:
    m = _CSV_RE.search(text or "")
    return m.group(1).strip() if m else None


def _local_name(tag: str) -> str:
    if not tag:
        return ""
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _find_first_text(root: ET.Element, *local_names: str) -> str | None:
    wanted = {str(n).strip() for n in local_names if str(n).strip()}
    if not wanted:
        return None
    for el in root.iter():
        if _local_name(el.tag) in wanted and el.text and str(el.text).strip():
            return str(el.text).strip()
    return None


def _parse_respuesta_reg_factu(cuerpo: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {
        "estado_registro": None,
        "csv": None,
        "codigo_error": None,
        "descripcion_error": None,
    }
    raw = (cuerpo or "").strip()
    if not raw:
        return out
    try:
        root = ET.fromstring(raw.encode("utf-8"))
    except ET.ParseError as exc:
        logger.warning(
            "Heurística AEAT: respuesta no es XML bien formado (ElementTree.ParseError): %s",
            exc,
        )
        return out
    except etree.XMLSyntaxError as exc:
        logger.warning(
            "Heurística AEAT: respuesta no es XML bien formado (lxml XMLSyntaxError): %s",
            exc,
        )
        return out
    except Exception:
        logger.exception(
            "Heurística AEAT: fallo inesperado parseando cuerpo para RegFactu (se usará heurística texto)"
        )
        return out
    out["estado_registro"] = _find_first_text(root, "EstadoRegistro", "Estado")
    out["csv"] = _find_first_text(
        root,
        "CSV",
        "CodigoSeguroVerificacion",
        "CodigoSeguroDeVerificacion",
    )
    out["codigo_error"] = _find_first_text(root, "CodigoErrorRegistro", "CodigoError")
    out["descripcion_error"] = _find_first_text(
        root,
        "DescripcionErrorRegistro",
        "DescripcionError",
    )
    return out


def interpretar_respuesta_aeat(
    *,
    cuerpo: str,
    http_status: int | None,
    post_result: RegFactuPostResult | None = None,
) -> AeatEnvioResultado:
    """
    Prioriza el resultado estructurado Zeep (WSDL oficial). Si no hay datos
    tipados, aplica la heurística histórica sobre XML/HTML/texto.
    """
    if post_result is not None:
        if post_result.soap_fault:
            return interpretar_respuesta_soap_fault(
                fault=post_result.soap_fault,
                http_status=post_result.http_status,
                raw_body=post_result.raw_body,
            )
        if post_result.respuesta is not None:
            return interpretar_respuesta_zeeo(
                parsed=cast(dict[str, Any], post_result.respuesta),
                http_status=post_result.http_status,
                raw_body=post_result.raw_body,
            )

    raw = (cuerpo or "")[:24000]
    low = raw.lower()
    parsed_xml = _parse_respuesta_reg_factu(raw)
    csv_val = (
        (parsed_xml.get("csv") or "").strip()
        or _extraer_csv(raw)
    ) or None
    estado_xml = str(parsed_xml.get("estado_registro") or "").strip().lower()
    cod_xml = (parsed_xml.get("codigo_error") or "").strip() or None
    desc_xml = (parsed_xml.get("descripcion_error") or "").strip() or None

    if http_status is not None and http_status >= 400:
        return AeatEnvioResultado(
            estado_envio_tabla="Error técnico",
            estado_factura_codigo="error_tecnico",
            codigo_error=cod_xml or str(http_status),
            descripcion_error=desc_xml or f"HTTP {http_status}",
            csv_aeat=csv_val,
            http_status=http_status,
            response_snippet=raw[:8000],
        )

    if estado_xml in {"correcto", "correcta"}:
        return AeatEnvioResultado(
            estado_envio_tabla="Aceptado",
            estado_factura_codigo="aceptado",
            codigo_error=None,
            descripcion_error=None,
            csv_aeat=csv_val,
            http_status=http_status,
            response_snippet=raw[:8000],
        )

    if estado_xml in {"aceptadoconerrores", "aceptado_con_errores"}:
        return AeatEnvioResultado(
            estado_envio_tabla="Aceptado con Errores",
            estado_factura_codigo="aceptado_con_errores",
            codigo_error=cod_xml,
            descripcion_error=desc_xml or (raw[:2000] if raw else None),
            csv_aeat=csv_val,
            http_status=http_status,
            response_snippet=raw[:8000],
        )

    if estado_xml in {"error", "rechazado", "incorrecto"}:
        return AeatEnvioResultado(
            estado_envio_tabla="Rechazado",
            estado_factura_codigo="rechazado",
            codigo_error=cod_xml,
            descripcion_error=desc_xml or (raw[:2000] if raw else None),
            csv_aeat=csv_val,
            http_status=http_status,
            response_snippet=raw[:8000],
        )

    if (
        "duplicad" in low
        or "ya existe" in low
        or "hash" in low
        or "huella" in low
        or "firma" in low
    ):
        return AeatEnvioResultado(
            estado_envio_tabla="Rechazado",
            estado_factura_codigo="rechazado",
            codigo_error=cod_xml,
            descripcion_error=desc_xml or (raw[:2000] if raw else None),
            csv_aeat=csv_val,
            http_status=http_status,
            response_snippet=raw[:8000],
        )

    if "rechaz" in low or "deneg" in low or "error grave" in low:
        return AeatEnvioResultado(
            estado_envio_tabla="Rechazado",
            estado_factura_codigo="rechazado",
            codigo_error=cod_xml,
            descripcion_error=desc_xml or (raw[:2000] if raw else None),
            csv_aeat=csv_val,
            http_status=http_status,
            response_snippet=raw[:8000],
        )

    if "aceptad" in low and ("error" in low or "advert" in low or "aviso" in low):
        return AeatEnvioResultado(
            estado_envio_tabla="Aceptado con Errores",
            estado_factura_codigo="aceptado_con_errores",
            codigo_error=cod_xml,
            descripcion_error=desc_xml or (raw[:2000] if raw else None),
            csv_aeat=csv_val,
            http_status=http_status,
            response_snippet=raw[:8000],
        )

    if "aceptad" in low or "correcto" in low or "procesad" in low:
        return AeatEnvioResultado(
            estado_envio_tabla="Aceptado",
            estado_factura_codigo="aceptado",
            codigo_error=cod_xml,
            descripcion_error=None,
            csv_aeat=csv_val,
            http_status=http_status,
            response_snippet=raw[:8000],
        )

    return AeatEnvioResultado(
        estado_envio_tabla="Aceptado con Errores",
        estado_factura_codigo="aceptado_con_errores",
        codigo_error=cod_xml,
        descripcion_error=(
            desc_xml
            or "Respuesta no reconocida; revise response_snippet / registros AEAT."
        ),
        csv_aeat=csv_val,
        http_status=http_status,
        response_snippet=raw[:8000],
    )


def url_envio_efectiva(settings: Settings) -> str | None:
    if not settings.AEAT_VERIFACTU_ENABLED:
        return None
    if settings.ENVIRONMENT == "development" and settings.AEAT_BLOQUEAR_PROD_EN_DESARROLLO:
        u = (settings.AEAT_VERIFACTU_SUBMIT_URL_TEST or "").strip()
        return u or None
    if settings.AEAT_VERIFACTU_USE_PRODUCTION:
        u = (settings.AEAT_VERIFACTU_SUBMIT_URL_PROD or "").strip()
        return u or None
    u = (settings.AEAT_VERIFACTU_SUBMIT_URL_TEST or "").strip()
    return u or None


def _tls_paths_desde_empresa_y_settings(
    empresa: Mapping[str, Any], settings: Settings
) -> tuple[str | None, str | None, str | None]:
    c = str(empresa.get("aeat_client_cert_path") or "").strip() or None
    k = str(empresa.get("aeat_client_key_path") or "").strip() or None
    p12 = str(empresa.get("aeat_client_p12_path") or "").strip() or None
    if not c:
        c = (settings.AEAT_CLIENT_CERT_PATH or "").strip() or None
    if not k:
        k = (settings.AEAT_CLIENT_KEY_PATH or "").strip() or None
    if not p12:
        p12 = (settings.AEAT_CLIENT_P12_PATH or "").strip() or None
    return c, k, p12


def _materializar_p12_a_pem(p12_path: str, password: str | None) -> tuple[str, str, list[str]]:
    pwd = password.encode("utf-8") if password else None
    with open(p12_path, "rb") as f:
        data = f.read()
    key, cert, _chain = pkcs12.load_key_and_certificates(data, pwd)
    if key is None or cert is None:
        raise ValueError("PKCS#12 sin clave o certificado legible")

    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cleanup: list[str] = []
    cf = tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem")
    kf = tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem")
    try:
        cf.write(cert_pem)
        kf.write(key_pem)
        cf.flush()
        kf.flush()
    finally:
        cf.close()
        kf.close()
    cleanup.extend([cf.name, kf.name])
    return cf.name, kf.name, cleanup


def _preparar_certificado_mtls(
    empresa: Mapping[str, Any], settings: Settings
) -> tuple[tuple[str, str] | None, list[str]]:
    """
    Devuelve ``(cert_path, key_path)`` para mTLS (``requests``/Zeep) y rutas a borrar.
    """
    c, k, p12 = _tls_paths_desde_empresa_y_settings(empresa, settings)
    cleanup: list[str] = []
    if p12 and os.path.isfile(p12):
        pwd = settings.AEAT_CLIENT_P12_PASSWORD or None
        cp, kp, extra = _materializar_p12_a_pem(p12, pwd)
        cleanup.extend(extra)
        return (cp, kp), cleanup
    if c and k and os.path.isfile(c) and os.path.isfile(k):
        return (c, k), cleanup
    return None, cleanup


def _limpiar_temp(paths: list[str]) -> None:
    for p in paths:
        try:
            if p and os.path.isfile(p):
                os.unlink(p)
        except OSError:
            pass


AEAT_HTTP_MAX_ATTEMPTS = 6
AEAT_BACKOFF_BASE_SEC = 1.5


def _post_reg_factu_soap_sync(
    *,
    url: str,
    soap_body: str,
    signed_inner_xml: str,
    cert_tuple: tuple[str, str],
    settings: Settings,
) -> tuple[int, str, RegFactuPostResult]:
    client = AeatSoapClient(
        cert_file=cert_tuple[0],
        key_file=cert_tuple[1],
        settings=settings,
    )
    try:
        out = client.submit_signed_soap(
            service_url=url,
            soap12_body=soap_body,
            signed_inner_xml=signed_inner_xml,
        )
        post_result = out.post_result
        return post_result.http_status, post_result.raw_body, post_result
    finally:
        client.close()


async def _post_soap_aeat_with_retries(
    *,
    url: str,
    soap_body: str,
    signed_inner_xml: str,
    cert_tuple: tuple[str, str],
    settings: Settings,
) -> tuple[int, str, RegFactuPostResult | None]:
    """
    Reintentos con backoff exponencial ante 429/5xx y errores de red (AEAT inestable).
    Los 4xx de validación (salvo 429) no se reintentan.

    El envío usa ``AEATZeepClient`` (Zeep + requests + mTLS) y parseo WSDL de respuesta.
    """
    delay = AEAT_BACKOFF_BASE_SEC
    last_exc: Exception | None = None
    for attempt in range(AEAT_HTTP_MAX_ATTEMPTS):
        try:

            def _sync() -> tuple[int, str, RegFactuPostResult]:
                return _post_reg_factu_soap_sync(
                    url=url,
                    soap_body=soap_body,
                    signed_inner_xml=signed_inner_xml,
                    cert_tuple=cert_tuple,
                    settings=settings,
                )

            code, text, zres = await asyncio.to_thread(_sync)
            if code in (429, 500, 502, 503, 504) and attempt < AEAT_HTTP_MAX_ATTEMPTS - 1:
                jitter = random.uniform(0.0, 0.35 * delay)
                logger.warning(
                    "AEAT HTTP %s intento %s/%s; reintento en %.2fs",
                    code,
                    attempt + 1,
                    AEAT_HTTP_MAX_ATTEMPTS,
                    delay + jitter,
                )
                await asyncio.sleep(delay + jitter)
                delay = min(delay * 2.0, 90.0)
                continue
            return code, text, zres
        except VeriFactuException as exc:
            if getattr(exc, "code", None) in {"XSD_REQUEST", "SOAP_MALFORMED"}:
                raise
            last_exc = exc
            if attempt < AEAT_HTTP_MAX_ATTEMPTS - 1:
                jitter = random.uniform(0.0, 0.35 * delay)
                logger.warning(
                    "AEAT cliente VeriFactu (%s) intento %s/%s; reintento en %.2fs",
                    type(exc).__name__,
                    attempt + 1,
                    AEAT_HTTP_MAX_ATTEMPTS,
                    delay + jitter,
                )
                await asyncio.sleep(delay + jitter)
                delay = min(delay * 2.0, 90.0)
                continue
            raise
    if last_exc:
        raise last_exc
    return 500, "", RegFactuPostResult(
        http_status=500,
        raw_body="",
        respuesta=None,
        soap_fault=None,
    )


def _leer_pem_certificado_y_clave(cert_path: str, key_path: str) -> tuple[bytes, bytes]:
    """Lee PEM en disco (mismo material que usa el cliente TLS para mTLS)."""
    with open(cert_path, "rb") as f:
        cert_pem = f.read()
    with open(key_path, "rb") as f:
        key_pem = f.read()
    return cert_pem, key_pem


def _password_clave_pem(settings: Settings) -> bytes | None:
    raw = settings.AEAT_CLIENT_KEY_PASSWORD
    if raw is None or not str(raw).strip():
        return None
    return str(raw).strip().encode("utf-8")


def _password_p12(settings: Settings) -> str | None:
    raw = getattr(settings, "AEAT_CLIENT_P12_PASSWORD", None)
    if raw is None or not str(raw).strip():
        return None
    return str(raw).strip()


def _extraer_registro_alta_firmado(xml_firmado: str) -> bytes:
    parser = etree.XMLParser(resolve_entities=False)
    root = etree.fromstring(xml_firmado.encode("utf-8"), parser=parser)
    if etree.QName(root.tag).localname == "RegistroAlta":
        return etree.tostring(root, xml_declaration=True, encoding="utf-8")
    matches = root.xpath(".//*[local-name()='RegistroAlta']")
    if not matches:
        raise ValueError("Firma XAdES sin nodo RegistroAlta en salida.")
    return etree.tostring(matches[0], xml_declaration=True, encoding="utf-8")


def _firmar_registro_alta(
    *,
    alta_xml: bytes,
    empresa_row: Mapping[str, Any],
    settings: Settings,
    cert_pem: bytes,
    key_pem: bytes,
    pwd: bytes | None,
) -> bytes:
    """
    Firma de compatibilidad:
    - Preferencia por ``crypto_service.sign_invoice_xml`` cuando hay .p12 disponible.
    - Fallback a firmador legacy PEM (``sign_xml_xades``).
    """
    try:
        _, _, p12_path = _tls_paths_desde_empresa_y_settings(empresa_row, settings)
    except AttributeError:
        p12_path = None
    if p12_path and os.path.isfile(p12_path):
        signed = sign_invoice_xml(
            alta_xml,
            p12_path,
            _password_p12(settings),
        )
        return _extraer_registro_alta_firmado(signed)
    return sign_xml_xades(
        alta_xml,
        cert_pem,
        key_pem,
        pwd,
    )


async def enviar_registro_y_persistir(
    db: SupabaseAsync,
    *,
    settings: Settings,
    empresa_id: str,
    empresa_row: Mapping[str, Any],
    factura_row: dict[str, Any],
    cliente: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Construye XML+SOAP, llama al endpoint si procede, inserta ``verifactu_envios`` y
    actualiza columnas ``aeat_sif_*`` en ``facturas``. Devuelve ``factura_row`` fusionado.
    """
    fid = int(factura_row["id"])
    now_iso = datetime.now(timezone.utc).isoformat()

    if not settings.AEAT_VERIFACTU_ENABLED:
        return factura_row

    url = url_envio_efectiva(settings)

    if not url:
        ins = {
            "empresa_id": empresa_id,
            "factura_id": fid,
            "estado": "Omitido",
            "codigo_error": None,
            "descripcion_error": "AEAT_VERIFACTU_ENABLED sin URL de envío configurada (use AEAT_VERIFACTU_SUBMIT_URL_TEST).",
            "csv_aeat": None,
            "http_status": None,
            "response_snippet": None,
            "soap_action": None,
            "created_at": now_iso,
        }
        await db.execute(db.table("verifactu_envios").insert(ins))
        await _patch_factura_aeat(
            db,
            empresa_id=empresa_id,
            factura_id=fid,
            estado="omitido",
            codigo=None,
            descripcion=ins["descripcion_error"],
            csv=None,
            actualizado_en=now_iso,
        )
        return {**factura_row, "aeat_sif_estado": "omitido"}

    cert_tuple, cleanup = _preparar_certificado_mtls(empresa_row, settings)
    if not cert_tuple:
        ins = {
            "empresa_id": empresa_id,
            "factura_id": fid,
            "estado": "Error técnico",
            "codigo_error": "CERT",
            "descripcion_error": "Falta certificado cliente TLS (.pem o .p12) o rutas no válidas.",
            "csv_aeat": None,
            "http_status": None,
            "response_snippet": None,
            "soap_action": None,
            "created_at": now_iso,
        }
        await db.execute(db.table("verifactu_envios").insert(ins))
        await _patch_factura_aeat(
            db,
            empresa_id=empresa_id,
            factura_id=fid,
            estado="error_tecnico",
            codigo="CERT",
            descripcion=ins["descripcion_error"],
            csv=None,
            actualizado_en=now_iso,
        )
        _limpiar_temp(cleanup)
        return {**factura_row, "aeat_sif_estado": "error_tecnico"}

    try:
        cert_pem, key_pem = _leer_pem_certificado_y_clave(cert_tuple[0], cert_tuple[1])
        pwd = _password_clave_pem(settings)

        prev_fp = str(factura_row.get("prev_fingerprint") or "").strip() or None
        registro_ant = await _obtener_registro_anterior_aeat(
            db, empresa_id=empresa_id, prev_fingerprint=prev_fp
        )
        rectificada_ref = await _obtener_factura_rectificada_aeat(
            db, empresa_id=empresa_id, factura=factura_row
        )
        alta_u = build_registro_alta_unsigned(
            factura=factura_row,
            empresa=empresa_row,
            cliente=cliente,
            fingerprint=str(factura_row.get("fingerprint") or "").strip(),
            registro_anterior=registro_ant,
            rectificada=rectificada_ref,
        )
        alta_xml = etree.tostring(
            alta_u,
            xml_declaration=True,
            encoding="utf-8",
        )

        def _sign_payload() -> bytes:
            return _firmar_registro_alta(
                alta_xml=alta_xml,
                empresa_row=empresa_row,
                settings=settings,
                cert_pem=cert_pem,
                key_pem=key_pem,
                pwd=pwd,
            )

        xml_firmado = await asyncio.to_thread(_sign_payload)
        xml_para_soap = inner_xml_fragment_from_signed_registro_alta(
            empresa=empresa_row,
            factura=factura_row,
            signed_registro_alta_xml=xml_firmado,
        )
        # Validación explícita del XML RegFactu antes de envolver en SOAP.
        if bool(getattr(settings, "AEAT_VERIFACTU_XSD_VALIDATE_REQUEST", False)):
            from app.services.verifactu_xml_service import VeriFactuXmlService

            VeriFactuXmlService().validate_against_regfactu_schema(
                '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_para_soap
            )
        asyncio.create_task(
            run_webhook_deliveries_for_event(
                empresa_id,
                WebhookEventType.VERIFACTU_INVOICE_SIGNED.value,
                {"factura_id": fid},
            )
        )
    except ValueError as exc:
        logger.warning("AEAT: validación o firma XAdES (ValueError) antes del envío: %s", exc)
        ins = {
            "empresa_id": empresa_id,
            "factura_id": fid,
            "estado": "Error técnico",
            "codigo_error": "XADES",
            "descripcion_error": f"Firma XAdES-BES: {str(exc)[:2000]}",
            "csv_aeat": None,
            "http_status": None,
            "response_snippet": None,
            "soap_action": None,
            "created_at": now_iso,
        }
        await db.execute(db.table("verifactu_envios").insert(ins))
        await _patch_factura_aeat(
            db,
            empresa_id=empresa_id,
            factura_id=fid,
            estado="error_tecnico",
            codigo="XADES",
            descripcion=ins["descripcion_error"],
            csv=None,
            actualizado_en=now_iso,
        )
        _limpiar_temp(cleanup)
        return {**factura_row, "aeat_sif_estado": "error_tecnico"}
    except OSError as exc:
        logger.warning("AEAT: lectura certificado/clave PEM (OSError): %s", exc)
        desc = f"Lectura certificado mTLS: {str(exc)[:2000]}"
        ins = {
            "empresa_id": empresa_id,
            "factura_id": fid,
            "estado": "Error técnico",
            "codigo_error": "CERT_READ",
            "descripcion_error": desc,
            "csv_aeat": None,
            "http_status": None,
            "response_snippet": None,
            "soap_action": None,
            "created_at": now_iso,
        }
        await db.execute(db.table("verifactu_envios").insert(ins))
        await _patch_factura_aeat(
            db,
            empresa_id=empresa_id,
            factura_id=fid,
            estado="error_tecnico",
            codigo="CERT_READ",
            descripcion=ins["descripcion_error"],
            csv=None,
            actualizado_en=now_iso,
        )
        _limpiar_temp(cleanup)
        return {**factura_row, "aeat_sif_estado": "error_tecnico"}
    except etree.XMLSyntaxError as exc:
        logger.warning("AEAT: XML mal formado antes del envío (lxml XMLSyntaxError): %s", exc)
        desc = f"XML registro: {str(exc)[:2000]}"
        ins = {
            "empresa_id": empresa_id,
            "factura_id": fid,
            "estado": "Error técnico",
            "codigo_error": "XML_SYNTAX",
            "descripcion_error": desc,
            "csv_aeat": None,
            "http_status": None,
            "response_snippet": None,
            "soap_action": None,
            "created_at": now_iso,
        }
        await db.execute(db.table("verifactu_envios").insert(ins))
        await _patch_factura_aeat(
            db,
            empresa_id=empresa_id,
            factura_id=fid,
            estado="error_tecnico",
            codigo="XML_SYNTAX",
            descripcion=ins["descripcion_error"],
            csv=None,
            actualizado_en=now_iso,
        )
        _limpiar_temp(cleanup)
        return {**factura_row, "aeat_sif_estado": "error_tecnico"}
    except Exception as exc:
        logger.exception("AEAT: error inesperado preparando registro firmado / sobre SOAP")
        ins = {
            "empresa_id": empresa_id,
            "factura_id": fid,
            "estado": "Error técnico",
            "codigo_error": "XADES",
            "descripcion_error": f"Firma XAdES-BES: {str(exc)[:2000]}",
            "csv_aeat": None,
            "http_status": None,
            "response_snippet": None,
            "soap_action": None,
            "created_at": now_iso,
        }
        await db.execute(db.table("verifactu_envios").insert(ins))
        await _patch_factura_aeat(
            db,
            empresa_id=empresa_id,
            factura_id=fid,
            estado="error_tecnico",
            codigo="XADES",
            descripcion=ins["descripcion_error"],
            csv=None,
            actualizado_en=now_iso,
        )
        _limpiar_temp(cleanup)
        return {**factura_row, "aeat_sif_estado": "error_tecnico"}

    inner_for_soap = xml_para_soap.strip()
    soap = envolver_soap12(inner_for_soap)
    try:
        status, body, zres = await _post_soap_aeat_with_retries(
            url=url,
            soap_body=soap,
            signed_inner_xml=inner_for_soap,
            cert_tuple=cert_tuple,
            settings=settings,
        )
    except VeriFactuException as exc:
        if getattr(exc, "code", None) in {"XSD_REQUEST", "SOAP_MALFORMED"}:
            ins = {
                "empresa_id": empresa_id,
                "factura_id": fid,
                "estado": "Error técnico",
                "codigo_error": str(getattr(exc, "code", None) or "XSD"),
                "descripcion_error": str(exc)[:2000],
                "csv_aeat": None,
                "http_status": None,
                "response_snippet": None,
                "soap_action": None,
                "created_at": now_iso,
            }
            await db.execute(db.table("verifactu_envios").insert(ins))
            await _patch_factura_aeat(
                db,
                empresa_id=empresa_id,
                factura_id=fid,
                estado="error_tecnico",
                codigo=str(getattr(exc, "code", None) or "XSD"),
                descripcion=ins["descripcion_error"],
                csv=None,
                actualizado_en=now_iso,
            )
            _limpiar_temp(cleanup)
            return {**factura_row, "aeat_sif_estado": "error_tecnico"}
        code_raw = str(getattr(exc, "code", None) or "").strip()
        detail_raw = getattr(exc, "detail", None)
        if code_raw == "AEAT_TRANSPORT":
            tk = _classify_transport_detail(detail_raw)
            if tk == "timeout":
                codigo_env = "AEAT_TIMEOUT"
                logger.warning(
                    "AEAT: tiempo de espera agotado tras reintentos HTTP (origen=%s)",
                    type(detail_raw).__name__ if detail_raw is not None else None,
                )
            elif tk == "connect":
                codigo_env = "AEAT_CONNECTION"
                logger.warning(
                    "AEAT: fallo de conexión tras reintentos HTTP (origen=%s)",
                    type(detail_raw).__name__ if detail_raw is not None else None,
                )
            else:
                codigo_env = "REINTENTO_AGOTADO"
                logger.warning(
                    "AEAT: error de transporte tras reintentos (code=%s origen=%s): %s",
                    code_raw,
                    type(detail_raw).__name__ if detail_raw is not None else None,
                    exc,
                )
        elif code_raw == "SOAP_FAULT":
            f_str = getattr(exc, "fault_string", None)
            f_code = getattr(exc, "fault_code", None)
            codigo_env = "SOAP_FAULT"
            logger.warning(
                "AEAT SOAP Fault (excepción cliente): fault_code=%r fault_string=%s",
                f_code,
                (str(f_str) if f_str is not None else str(exc))[:1500],
            )
        else:
            codigo_env = "REINTENTO_AGOTADO"
            logger.exception("AEAT: VeriFactuException tras reintentos (code=%r)", code_raw)

        descr_vfe = str(exc)[:2000]
        if code_raw == "SOAP_FAULT":
            fs = getattr(exc, "fault_string", None)
            descr_vfe = (str(fs) if fs is not None else str(exc))[:2000]

        ins = {
            "empresa_id": empresa_id,
            "factura_id": fid,
            "estado": "Pendiente de envío (cola)",
            "codigo_error": codigo_env,
            "descripcion_error": descr_vfe,
            "csv_aeat": None,
            "http_status": getattr(exc, "http_status", None),
            "response_snippet": None,
            "soap_action": "RegistroFactura",
            "created_at": now_iso,
        }
        await db.execute(db.table("verifactu_envios").insert(ins))
        await _patch_factura_aeat(
            db,
            empresa_id=empresa_id,
            factura_id=fid,
            estado="pendiente_envio",
            codigo=codigo_env,
            descripcion=ins["descripcion_error"],
            csv=None,
            actualizado_en=now_iso,
        )
        _limpiar_temp(cleanup)
        return {**factura_row, "aeat_sif_estado": "pendiente_envio"}
    except Exception as exc:
        logger.exception("AEAT: error no clasificado durante POST SOAP / red")
        ins = {
            "empresa_id": empresa_id,
            "factura_id": fid,
            "estado": "Pendiente de envío (cola)",
            "codigo_error": "REINTENTO_AGOTADO",
            "descripcion_error": str(exc)[:2000],
            "csv_aeat": None,
            "http_status": None,
            "response_snippet": None,
            "soap_action": "RegistroFactura",
            "created_at": now_iso,
        }
        await db.execute(db.table("verifactu_envios").insert(ins))
        await _patch_factura_aeat(
            db,
            empresa_id=empresa_id,
            factura_id=fid,
            estado="pendiente_envio",
            codigo="REINTENTO_AGOTADO",
            descripcion=ins["descripcion_error"],
            csv=None,
            actualizado_en=now_iso,
        )
        _limpiar_temp(cleanup)
        return {**factura_row, "aeat_sif_estado": "pendiente_envio"}

    if zres is not None and zres.soap_fault:
        ff = zres.soap_fault
        logger.warning(
            "AEAT SOAP Fault (cuerpo HTTP): faultcode=%r faultstring=%s http_status=%s",
            ff.get("faultcode"),
            (str(ff.get("faultstring") or "")[:1500]),
            status,
        )

    if status is not None and (status >= 500 or status == 429):
        ins = {
            "empresa_id": empresa_id,
            "factura_id": fid,
            "estado": "Pendiente de envío (5xx/429)",
            "codigo_error": str(status),
            "descripcion_error": (body or "")[:2000],
            "csv_aeat": None,
            "http_status": status,
            "response_snippet": (body or "")[:8000],
            "soap_action": "RegistroFactura",
            "created_at": now_iso,
        }
        await db.execute(db.table("verifactu_envios").insert(ins))
        await _patch_factura_aeat(
            db,
            empresa_id=empresa_id,
            factura_id=fid,
            estado="pendiente_envio",
            codigo=str(status),
            descripcion=ins["descripcion_error"],
            csv=None,
            actualizado_en=now_iso,
        )
        _limpiar_temp(cleanup)
        return {**factura_row, "aeat_sif_estado": "pendiente_envio"}

    _limpiar_temp(cleanup)

    parsed = interpretar_respuesta_aeat(
        cuerpo=body, http_status=status, post_result=zres
    )
    ins = {
        "empresa_id": empresa_id,
        "factura_id": fid,
        "estado": parsed.estado_envio_tabla,
        "codigo_error": parsed.codigo_error,
        "descripcion_error": parsed.descripcion_error,
        "csv_aeat": parsed.csv_aeat,
        "http_status": status,
        "response_snippet": parsed.response_snippet,
        "soap_action": "RegistroFactura",
        "created_at": now_iso,
    }
    await db.execute(db.table("verifactu_envios").insert(ins))
    await _patch_factura_aeat(
        db,
        empresa_id=empresa_id,
        factura_id=fid,
        estado=parsed.estado_factura_codigo,
        codigo=parsed.codigo_error,
        descripcion=parsed.descripcion_error,
        csv=parsed.csv_aeat,
        actualizado_en=now_iso,
    )
    return {
        **factura_row,
        "aeat_sif_estado": parsed.estado_factura_codigo,
        "aeat_sif_csv": parsed.csv_aeat,
        "aeat_sif_codigo": parsed.codigo_error,
        "aeat_sif_descripcion": parsed.descripcion_error,
        "aeat_sif_actualizado_en": now_iso,
    }


async def _patch_factura_aeat(
    db: SupabaseAsync,
    *,
    empresa_id: str,
    factura_id: int,
    estado: str,
    codigo: str | None,
    descripcion: str | None,
    csv: str | None,
    actualizado_en: str,
) -> None:
    payload: dict[str, Any] = {
        "aeat_sif_estado": estado,
        "aeat_sif_csv": csv,
        "aeat_sif_codigo": codigo,
        "aeat_sif_descripcion": descripcion,
        "aeat_sif_actualizado_en": actualizado_en,
    }
    await db.execute(
        db.table("facturas")
        .update({k: v for k, v in payload.items()})
        .eq("id", factura_id)
        .eq("empresa_id", empresa_id)
    )


async def enviar_factura_aeat(factura_id: str) -> dict[str, Any]:
    """
    Envía una factura finalizada a AEAT VeriFactu con SOAP 1.2 + mTLS.
    """
    fid_raw = str(factura_id or "").strip()
    if not fid_raw:
        raise ValueError("factura_id es obligatorio")
    try:
        fid = int(fid_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("factura_id inválido") from exc

    settings = get_settings()
    db = await get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )

    rf: Any = await db.execute(db.table("facturas").select("*").eq("id", fid).limit(1))
    frows: list[dict[str, Any]] = (rf.data or []) if hasattr(rf, "data") else []
    if not frows:
        raise ValueError("Factura no encontrada")
    factura_row = dict(frows[0])
    if not bool(factura_row.get("is_finalized")):
        raise ValueError("Solo se puede enviar a la AEAT una factura finalizada")

    empresa_id = str(factura_row.get("empresa_id") or "").strip()
    if not empresa_id:
        raise ValueError("Factura sin empresa_id")

    raw_nif = factura_row.get("nif_emisor")
    if isinstance(raw_nif, str) and raw_nif.strip():
        factura_row["nif_emisor"] = pii_crypto.decrypt_pii(raw_nif) or raw_nif

    re: Any = await db.execute(db.table("empresas").select("*").eq("id", empresa_id).limit(1))
    erows: list[dict[str, Any]] = (re.data or []) if hasattr(re, "data") else []
    if not erows:
        raise ValueError("Empresa no encontrada")
    empresa_row = dict(erows[0])
    raw_emp_nif = empresa_row.get("nif")
    if isinstance(raw_emp_nif, str) and raw_emp_nif.strip():
        empresa_row["nif"] = pii_crypto.decrypt_pii(raw_emp_nif) or raw_emp_nif

    cliente_map: dict[str, Any] = {"nif": "", "nombre": ""}
    cid = str(factura_row.get("cliente") or "").strip()
    if cid:
        try:
            rc: Any = await db.execute(
                filter_not_deleted(
                    db.table("clientes")
                    .select("*")
                    .eq("empresa_id", empresa_id)
                    .eq("id", cid)
                    .limit(1)
                )
            )
            crows: list[dict[str, Any]] = (rc.data or []) if hasattr(rc, "data") else []
            if crows:
                cli = dict(crows[0])
                raw_cli_nif = cli.get("nif")
                if isinstance(raw_cli_nif, str) and raw_cli_nif.strip():
                    cli["nif"] = pii_crypto.decrypt_pii(raw_cli_nif) or raw_cli_nif
                cliente_map = {
                    "nif": str(cli.get("nif") or "").strip(),
                    "nombre": str(cli.get("nombre") or "").strip(),
                }
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            logger.warning(
                "AEAT enviar_factura_aeat: datos de cliente incompletos o ilegibles (cliente_id=%s): %s",
                cid,
                exc,
            )
            cliente_map = {"nif": "", "nombre": ""}
        except Exception:
            logger.exception(
                "AEAT enviar_factura_aeat: fallo inesperado al cargar cliente_id=%s; se continúa sin datos de cliente",
                cid,
            )
            cliente_map = {"nif": "", "nombre": ""}

    return await enviar_registro_y_persistir(
        db,
        settings=settings,
        empresa_id=empresa_id,
        empresa_row=empresa_row,
        factura_row=factura_row,
        cliente=cliente_map,
    )
