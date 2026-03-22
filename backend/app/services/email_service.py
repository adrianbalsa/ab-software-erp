from __future__ import annotations

import base64
import logging
import re
from typing import Any

import resend

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _resend_configured() -> bool:
    s = get_settings()
    return bool(s.RESEND_API_KEY and s.EMAIL_FROM_ADDRESS)


def _normalize_dest_email(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    e = str(raw).strip()
    if not _EMAIL_RE.match(e):
        return None
    return e


def _invoice_html(factura_data: dict[str, Any]) -> str:
    num = str(factura_data.get("numero_factura") or "—")
    fecha = str(factura_data.get("fecha_emision") or "—")
    total = factura_data.get("total_factura")
    base = factura_data.get("base_imponible")
    iva = factura_data.get("cuota_iva")
    emp = str(factura_data.get("empresa_nombre") or "AB Logistics OS")
    cli = str(factura_data.get("cliente_nombre") or "Cliente")

    def fmt_eur(v: Any) -> str:
        try:
            return f"{float(v):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        except (TypeError, ValueError):
            return "—"

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width"/></head>
<body style="margin:0;padding:0;background-color:#18181b;font-family:system-ui,-apple-system,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#18181b;padding:24px 12px;">
    <tr><td align="center">
      <table width="600" style="max-width:600px;background:#27272a;border-radius:12px;overflow:hidden;border:1px solid #3f3f46;">
        <tr>
          <td style="padding:24px 28px;background:linear-gradient(135deg,#27272a 0%,#14532d 100%);border-bottom:1px solid #3f3f46;">
            <p style="margin:0;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#a1a1aa;">AB Logistics OS</p>
            <h1 style="margin:8px 0 0;font-size:20px;font-weight:700;color:#fafafa;">Nueva factura emitida</h1>
            <p style="margin:8px 0 0;font-size:14px;color:#d4d4d8;">{emp}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:24px 28px;color:#e4e4e7;font-size:15px;line-height:1.6;">
            <p style="margin:0 0 16px;">Hola <strong style="color:#fafafa;">{cli}</strong>,</p>
            <p style="margin:0 0 20px;">Adjuntamos el PDF de tu factura con huella VeriFactu.</p>
            <table width="100%" style="border-collapse:collapse;font-size:14px;">
              <tr><td style="padding:8px 0;color:#a1a1aa;">Número</td><td align="right" style="padding:8px 0;color:#fafafa;font-weight:600;">{num}</td></tr>
              <tr><td style="padding:8px 0;color:#a1a1aa;">Fecha</td><td align="right" style="padding:8px 0;color:#fafafa;">{fecha}</td></tr>
              <tr><td style="padding:8px 0;color:#a1a1aa;">Base imponible</td><td align="right" style="padding:8px 0;">{fmt_eur(base)}</td></tr>
              <tr><td style="padding:8px 0;color:#a1a1aa;">IVA</td><td align="right" style="padding:8px 0;">{fmt_eur(iva)}</td></tr>
              <tr><td colspan="2" style="border-top:1px solid #3f3f46;padding-top:12px;"></td></tr>
              <tr><td style="padding:8px 0;color:#6ee7b7;font-weight:600;">Total</td><td align="right" style="padding:8px 0;color:#6ee7b7;font-size:18px;font-weight:700;">{fmt_eur(total)}</td></tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 28px;background:#1f1f23;font-size:12px;color:#71717a;border-top:1px solid #3f3f46;">
            Mensaje generado automáticamente. No respondas a este correo.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _quota_html(empresa_email: str, current_count: int, limit: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"/></head>
<body style="margin:0;padding:0;background-color:#18181b;font-family:system-ui,sans-serif;">
  <table width="100%" style="background:#18181b;padding:24px;"><tr><td align="center">
    <table width="560" style="max-width:560px;background:#27272a;border-radius:12px;border:1px solid #3f3f46;">
      <tr><td style="padding:24px 28px;background:linear-gradient(135deg,#27272a,#14532d);">
        <h1 style="margin:0;font-size:18px;color:#fafafa;">Alerta de cuota de flota</h1>
        <p style="margin:8px 0 0;font-size:13px;color:#a1a1aa;">{empresa_email}</p>
      </td></tr>
      <tr><td style="padding:24px;color:#e4e4e7;font-size:14px;line-height:1.6;">
        <p>Has alcanzado <strong style="color:#6ee7b7;">{current_count}</strong> de <strong>{limit}</strong> vehículos permitidos por tu plan.</p>
        <p style="margin:16px 0 0;color:#a1a1aa;font-size:13px;">Mejora de plan para seguir operando sin interrupciones.</p>
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""


def send_invoice_email_from_base64(
    factura_data: dict[str, Any],
    pdf_base64: str | None,
    dest_email: str | None,
) -> bool:
    """
    Decodifica ``pdf_base64`` y delega en ``send_invoice_email``.
    Útil para ``BackgroundTasks`` tras ``POST /facturas/desde-portes``.
    """
    if not pdf_base64 or not dest_email:
        return False
    try:
        pdf_bytes = base64.b64decode(pdf_base64.encode("ascii"))
    except Exception as exc:
        logger.warning("No se pudo decodificar PDF base64 para email: %s", exc)
        return False
    return send_invoice_email(factura_data, pdf_bytes, dest_email)


def send_invoice_email(
    factura_data: dict[str, Any],
    pdf_content: bytes,
    dest_email: str,
) -> bool:
    """
    Envía la factura en PDF por correo (Resend). No lanza si falta configuración o destino inválido.
    """
    dest = _normalize_dest_email(dest_email)
    if not dest:
        logger.info("email factura omitido: destino no válido o vacío")
        return False

    if not _resend_configured():
        logger.warning("Resend no configurado (RESEND_API_KEY / EMAIL_FROM_ADDRESS); no se envía factura")
        return False

    if not pdf_content:
        logger.warning("email factura omitido: PDF vacío")
        return False

    settings = get_settings()
    assert settings.RESEND_API_KEY and settings.EMAIL_FROM_ADDRESS
    resend.api_key = settings.RESEND_API_KEY

    num = str(factura_data.get("numero_factura") or "factura")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in num)[:80]
    filename = f"Factura_{safe_name}.pdf"

    try:
        params: dict[str, Any] = {
            "from": settings.EMAIL_FROM_ADDRESS,
            "to": [dest],
            "subject": f"Factura {num} · AB Logistics OS",
            "html": _invoice_html(factura_data),
            "attachments": [
                {
                    "filename": filename,
                    # SDK Resend: bytes como lista de int, o string base64
                    "content": list(pdf_content),
                }
            ],
        }
        resend.Emails.send(params)
        logger.info("email factura enviado (numero_factura=%s)", num)
        return True
    except Exception as exc:
        logger.exception("Fallo al enviar email de factura: %s", exc)
        return False


def send_quota_alert(empresa_email: str, current_count: int, limit: int) -> bool:
    """Aviso de cuota de vehículos (admin / empresa)."""
    dest = _normalize_dest_email(empresa_email)
    if not dest:
        return False
    if not _resend_configured():
        logger.warning("Resend no configurado; no se envía alerta de cuota")
        return False

    settings = get_settings()
    assert settings.RESEND_API_KEY and settings.EMAIL_FROM_ADDRESS
    resend.api_key = settings.RESEND_API_KEY

    try:
        resend.Emails.send(
            {
                "from": settings.EMAIL_FROM_ADDRESS,
                "to": [dest],
                "subject": f"Alerta: {current_count}/{limit} vehículos · AB Logistics OS",
                "html": _quota_html(dest, current_count, limit),
            }
        )
        logger.info("alerta cuota enviada (current=%s limit=%s)", current_count, limit)
        return True
    except Exception as exc:
        logger.exception("Fallo al enviar alerta de cuota: %s", exc)
        return False
