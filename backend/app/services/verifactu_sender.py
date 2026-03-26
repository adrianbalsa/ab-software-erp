"""
Generación de XML de registro de facturación (VeriFactu / SIF 1.0, estructura lógica)
y envío HTTP(S) con autenticación mutua (mTLS) hacia endpoints configurables (pruebas / producción).

La remisión oficial AEAT suele ser SOAP firmado; aquí se encapsula el registro en SOAP 1.2
y se envía por POST. Ajuste ``AEAT_VERIFACTU_SUBMIT_URL_*`` al endpoint que indique la
documentación vigente (Anexo entorno de pruebas / producción).

Sin ``AEAT_VERIFACTU_ENABLED=true`` o sin URL/certificado, no se realiza llamada HTTP.
"""

from __future__ import annotations

import io
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from xml.etree import ElementTree as ET

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from app.core.config import Settings
from app.db.supabase import SupabaseAsync


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


def envolver_soap12(cuerpo_xml_sin_decl: str) -> str:
    """Envoltorio SOAP 1.2 mínimo alrededor del fragmento XML interno."""
    inner = cuerpo_xml_sin_decl.strip()
    if inner.startswith("<?xml"):
        inner = re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", inner, count=1)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">\n'
        "  <soap12:Body>\n"
        f"{inner}\n"
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


def interpretar_respuesta_aeat(*, cuerpo: str, http_status: int | None) -> AeatEnvioResultado:
    """
    Heurística sobre XML/HTML/texto de respuesta hasta contar con validación de esquema oficial.
    """
    raw = (cuerpo or "")[:24000]
    low = raw.lower()
    csv_val = _extraer_csv(raw)

    if http_status is not None and http_status >= 400:
        return AeatEnvioResultado(
            estado_envio_tabla="Error técnico",
            estado_factura_codigo="error_tecnico",
            codigo_error=str(http_status),
            descripcion_error=f"HTTP {http_status}",
            csv_aeat=csv_val,
            http_status=http_status,
            response_snippet=raw[:8000],
        )

    if "rechaz" in low or "deneg" in low or "error grave" in low:
        return AeatEnvioResultado(
            estado_envio_tabla="Rechazado",
            estado_factura_codigo="rechazado",
            codigo_error=None,
            descripcion_error=raw[:2000] if raw else None,
            csv_aeat=csv_val,
            http_status=http_status,
            response_snippet=raw[:8000],
        )

    if "aceptad" in low and ("error" in low or "advert" in low or "aviso" in low):
        return AeatEnvioResultado(
            estado_envio_tabla="Aceptado con Errores",
            estado_factura_codigo="aceptado_con_errores",
            codigo_error=None,
            descripcion_error=raw[:2000] if raw else None,
            csv_aeat=csv_val,
            http_status=http_status,
            response_snippet=raw[:8000],
        )

    if "aceptad" in low or "correcto" in low or "procesad" in low:
        return AeatEnvioResultado(
            estado_envio_tabla="Aceptado",
            estado_factura_codigo="aceptado",
            codigo_error=None,
            descripcion_error=None,
            csv_aeat=csv_val,
            http_status=http_status,
            response_snippet=raw[:8000],
        )

    return AeatEnvioResultado(
        estado_envio_tabla="Aceptado con Errores",
        estado_factura_codigo="aceptado_con_errores",
        codigo_error=None,
        descripcion_error="Respuesta no reconocida; revise response_snippet / registros AEAT.",
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
    xml_payload = generar_xml_registro_facturacion_alta(
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

    url = url_envio_efectiva(settings)
    now_iso = datetime.now(timezone.utc).isoformat()

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

    soap = envolver_soap12(
        re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", xml_payload.strip(), count=1)
    )
    status: int | None = None
    body = ""
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
                content=soap.encode("utf-8"),
                headers={
                    "Content-Type": 'application/soap+xml; charset=utf-8; action="RegistroFactura"',
                },
            )
            status = r.status_code
            body = r.text or ""
    except httpx.RequestError as exc:
        ins = {
            "empresa_id": empresa_id,
            "factura_id": fid,
            "estado": "Error técnico",
            "codigo_error": "HTTPX",
            "descripcion_error": str(exc)[:2000],
            "csv_aeat": None,
            "http_status": status,
            "response_snippet": body[:8000] if body else None,
            "soap_action": "RegistroFactura",
        }
        await db.execute(db.table("verifactu_envios").insert(ins))
        await _patch_factura_aeat(
            db,
            empresa_id=empresa_id,
            factura_id=fid,
            estado="error_tecnico",
            codigo="HTTPX",
            descripcion=ins["descripcion_error"],
            csv=None,
            actualizado_en=now_iso,
        )
        _limpiar_temp(cleanup)
        return {**factura_row, "aeat_sif_estado": "error_tecnico"}
    finally:
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
