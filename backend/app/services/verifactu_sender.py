"""
Generación de XML de registro de facturación (VeriFactu / SIF 1.0, estructura lógica),
**firma XAdES-BES** del fragmento de registro y envío HTTP(S) con autenticación mutua
(mTLS) hacia endpoints configurables (pruebas / producción).

Flujo: XML registro → firma digital enveloped (``ds:Signature`` + metadatos XAdES) →
envoltorio SOAP 1.2 → POST. El certificado de cliente TLS y el de firma XML deben ser
el mismo par (o al menos el admitido por la AEAT para el NIF/empresa).

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
import io
import logging
import os
import random
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from xml.etree import ElementTree as ET

import anyio
import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from app.core.config import Settings
from app.core.config import get_settings
from app.core.crypto import pii_crypto
from app.core.xades_signer import sign_xml_xades
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.db.supabase import get_supabase
from app.models.webhook import WebhookEventType
from app.services.webhook_service import run_webhook_deliveries_for_event

logger = logging.getLogger(__name__)

_NS_SOAP12 = "http://www.w3.org/2003/05/soap-envelope"
_NS_SF_DEFAULT = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/"
    "es/aeat/tikeV1.0/cont/ws/SuministroLR.xsd"
)
_NS_SJE_DEFAULT = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/"
    "es/aeat/tikeV1.0/cont/ws/SuministroInformacion.xsd"
)


def _txt(parent: ET.Element, tag: str, value: Any) -> None:
    el = ET.SubElement(parent, tag)
    if value is None:
        el.text = ""
    else:
        el.text = str(value).strip()


def generar_xml_registro_facturacion_alta(
    *,
    factura: Mapping[str, Any],
    empresa: Mapping[str, Any],
    cliente: Mapping[str, Any],
    hash_registro: str,
    fingerprint: str,
    prev_fingerprint: str | None,
) -> str:
    """
    XML de **Registro de Facturación Alta** (formato lógico 1.0, alineado con ``aeat_xml_service``).

    Incluye ``HashRegistro`` (cadena histórica al emitir), ``Huella`` (fingerprint final)
    y ``HuellaAnterior`` (prev_fingerprint de cadena de finalización).
    """
    num = str(
        factura.get("num_factura") or factura.get("numero_factura") or ""
    ).strip()
    fecha = str(factura.get("fecha_emision") or "").strip()
    if len(fecha) >= 10:
        fecha = fecha[:10]

    try:
        base = float(factura.get("base_imponible") or 0.0)
    except (TypeError, ValueError):
        base = 0.0
    try:
        cuota = float(factura.get("cuota_iva") or 0.0)
    except (TypeError, ValueError):
        cuota = 0.0
    try:
        total = float(factura.get("total_factura") or 0.0)
    except (TypeError, ValueError):
        total = 0.0

    tipo = str(factura.get("tipo_factura") or "F1").strip().upper() or "F1"
    nif_emisor = str(factura.get("nif_emisor") or empresa.get("nif") or "").strip()
    nif_dest = str(cliente.get("nif") or "").strip()

    tipo_iva_pct: float | None = None
    if base and abs(base) > 1e-9:
        try:
            tipo_iva_pct = round((cuota / base) * 100.0, 2)
        except (ZeroDivisionError, TypeError, ValueError):
            tipo_iva_pct = None

    nombre_emisor = str(
        empresa.get("nombre_comercial") or empresa.get("nombre_legal") or ""
    ).strip()
    nombre_dest = str(cliente.get("nombre") or "").strip()

    root = ET.Element("RegistroFacturacionAltaVeriFactu")
    root.set("versionFormato", "1.0")

    cab = ET.SubElement(root, "Cabecera")
    _txt(cab, "IdVersion", "1.0")
    _txt(cab, "NIFEmisor", nif_emisor)
    _txt(cab, "NombreEmisor", nombre_emisor or nif_emisor)

    reg = ET.SubElement(root, "RegistroFactura")
    _txt(reg, "NumeroFactura", num)
    _txt(reg, "FechaExpedicion", fecha)
    _txt(reg, "TipoFactura", tipo)
    _txt(reg, "NIFDestinatario", nif_dest)
    _txt(reg, "NombreDestinatario", nombre_dest or nif_dest)
    _txt(reg, "ImporteTotal", f"{total:.2f}")
    _txt(reg, "HashRegistro", str(hash_registro).strip())
    _txt(reg, "Huella", str(fingerprint).strip())
    if prev_fingerprint and str(prev_fingerprint).strip():
        _txt(reg, "HuellaAnterior", str(prev_fingerprint).strip())
    else:
        _txt(reg, "HuellaAnterior", "")

    rect_id = factura.get("factura_rectificada_id")
    if rect_id is not None:
        _txt(reg, "FacturaRectificadaId", str(rect_id).strip())
    motivo = factura.get("motivo_rectificacion")
    if motivo:
        _txt(reg, "MotivoRectificacion", str(motivo).strip()[:500])

    des = ET.SubElement(root, "DesgloseIVA")
    _txt(des, "BaseImponible", f"{base:.2f}")
    _txt(des, "CuotaIVA", f"{cuota:.2f}")
    if tipo_iva_pct is not None:
        _txt(des, "TipoImpositivo", f"{tipo_iva_pct:.2f}")

    tree = ET.ElementTree(root)
    buf = io.BytesIO()
    tree.write(buf, encoding="utf-8", xml_declaration=True)
    return buf.getvalue().decode("utf-8")


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
    except Exception:
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


def interpretar_respuesta_aeat(*, cuerpo: str, http_status: int | None) -> AeatEnvioResultado:
    """
    Heurística sobre XML/HTML/texto de respuesta hasta contar con validación de esquema oficial.
    """
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
    Devuelve ``(cert_path, key_path)`` para ``httpx.AsyncClient(cert=...)`` y rutas a borrar.
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


async def _post_soap_aeat_with_retries(
    *,
    url: str,
    soap_body: str,
    cert_tuple: tuple[str, str],
) -> tuple[int, str]:
    """
    Reintentos con backoff exponencial ante 429/5xx y errores de red (AEAT inestable).
    Los 4xx de validación (salvo 429) no se reintentan.
    """
    delay = AEAT_BACKOFF_BASE_SEC
    last_exc: Exception | None = None
    for attempt in range(AEAT_HTTP_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(
                http2=False,
                cert=cert_tuple,
                verify=True,
                timeout=httpx.Timeout(120.0),
                follow_redirects=False,
            ) as client:
                r = await client.post(
                    url,
                    content=soap_body.encode("utf-8"),
                    headers={
                        "Content-Type": 'application/soap+xml; charset=utf-8; action="RegistroFactura"',
                    },
                )
                code = r.status_code
                text = r.text or ""
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
                return code, text
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt < AEAT_HTTP_MAX_ATTEMPTS - 1:
                jitter = random.uniform(0.0, 0.35 * delay)
                logger.warning(
                    "AEAT red error (%s) intento %s/%s; reintento en %.2fs",
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
    return 500, ""


def _leer_pem_certificado_y_clave(cert_path: str, key_path: str) -> tuple[bytes, bytes]:
    """Lee PEM en disco (mismo material que usa ``httpx`` para mTLS)."""
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
    url = url_envio_efectiva(settings)
    now_iso = datetime.now(timezone.utc).isoformat()
    xml_payload_persistido = str(factura_row.get("xml_verifactu") or "").strip()
    xml_payload = xml_payload_persistido or generar_xml_registro_facturacion_alta(
        factura=factura_row,
        empresa=empresa_row,
        cliente=cliente,
        hash_registro=str(
            factura_row.get("hash_registro") or factura_row.get("hash_factura") or ""
        ).strip(),
        fingerprint=str(factura_row.get("fingerprint") or "").strip(),
        prev_fingerprint=(
            str(factura_row.get("prev_fingerprint") or "").strip() or None
        ),
    )

    if not settings.AEAT_VERIFACTU_ENABLED:
        return factura_row

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

        def _sign_payload() -> bytes:
            return sign_xml_xades(
                xml_payload.encode("utf-8"),
                cert_pem,
                key_pem,
                pwd,
            )

        xml_firmado = await anyio.to_thread.run_sync(_sign_payload)
        xml_para_soap = xml_firmado.decode("utf-8")
        asyncio.create_task(
            run_webhook_deliveries_for_event(
                empresa_id,
                WebhookEventType.VERIFACTU_INVOICE_SIGNED.value,
                {"factura_id": fid},
            )
        )
    except Exception as exc:
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

    soap = envolver_soap12(
        re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", xml_para_soap.strip(), count=1)
    )
    try:
        status, body = await _post_soap_aeat_with_retries(
            url=url,
            soap_body=soap,
            cert_tuple=cert_tuple,
        )
    except Exception as exc:
        logger.exception("AEAT: agotados reintentos HTTP/red")
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

    parsed = interpretar_respuesta_aeat(cuerpo=body, http_status=status)
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
        except Exception:
            cliente_map = {"nif": "", "nombre": ""}

    return await enviar_registro_y_persistir(
        db,
        settings=settings,
        empresa_id=empresa_id,
        empresa_row=empresa_row,
        factura_row=factura_row,
        cliente=cliente_map,
    )
