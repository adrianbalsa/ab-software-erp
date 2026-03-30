from __future__ import annotations

import asyncio
import base64
import html
import logging
import re
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

import resend

from app.core.config import Settings, get_settings

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


def _onboarding_invite_html(onboarding_link: str) -> str:
    safe_link = str(onboarding_link or "").strip()
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"/></head>
<body style="margin:0;padding:0;background-color:#18181b;font-family:system-ui,sans-serif;">
  <table width="100%" style="background:#18181b;padding:24px;"><tr><td align="center">
    <table width="560" style="max-width:560px;background:#27272a;border-radius:12px;border:1px solid #3f3f46;">
      <tr><td style="padding:24px 28px;background:linear-gradient(135deg,#27272a,#14532d);">
        <h1 style="margin:0;font-size:20px;color:#fafafa;">Invitación al onboarding</h1>
        <p style="margin:8px 0 0;font-size:13px;color:#a1a1aa;">AB Logistics OS</p>
      </td></tr>
      <tr><td style="padding:24px;color:#e4e4e7;font-size:14px;line-height:1.6;">
        <p>Hemos reenviado tu invitación para completar el onboarding.</p>
        <p style="margin:18px 0;">
          <a href="{safe_link}" style="display:inline-block;background:#16a34a;color:#ffffff;text-decoration:none;padding:10px 16px;border-radius:8px;font-weight:600;">
            Continuar onboarding
          </a>
        </p>
        <p style="margin:0;color:#a1a1aa;font-size:12px;word-break:break-all;">Si el botón no funciona, copia este enlace en tu navegador: {safe_link}</p>
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


def _safe_attachment_name_part(factura_num: str) -> str:
    s = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(factura_num).strip())[:120]
    return s or "factura"


def _invoice_smtp_html_simple(factura_num: str) -> str:
    """HTML sin incrustar nombre de fichero duplicado (evita doble escape en plantilla)."""
    num = html.escape(str(factura_num).strip() or "—")
    safe_file = html.escape(_safe_attachment_name_part(factura_num))
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f4f5;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" style="max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;
        box-shadow:0 4px 24px rgba(15,23,42,0.08);border:1px solid #e4e4e7;">
        <tr>
          <td style="padding:28px 32px;background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);">
            <p style="margin:0;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:#94a3b8;">
              Documento fiscal
            </p>
            <h1 style="margin:10px 0 0;font-size:22px;font-weight:700;color:#f8fafc;line-height:1.25;">
              Su factura está lista
            </h1>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px;color:#3f3f46;font-size:15px;line-height:1.65;">
            <p style="margin:0 0 16px;">Estimado cliente,</p>
            <p style="margin:0 0 20px;">
              Adjuntamos en PDF la factura <strong style="color:#0f172a;">{num}</strong>, emitida conforme a la normativa
              de facturación electrónica aplicable (VeriFactu / SIF).
            </p>
            <p style="margin:0;font-size:13px;color:#71717a;">
              Nombre del adjunto: <code style="background:#f4f4f5;padding:2px 8px;border-radius:6px;">Factura_{safe_file}.pdf</code>
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:20px 32px;background:#fafafa;border-top:1px solid #e4e4e7;font-size:12px;color:#71717a;">
            Mensaje generado automáticamente. Consulte con su contacto comercial para dudas sobre el documento.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _send_invoice_smtp_sync(
    settings: Settings,
    to_email: str,
    pdf_content: bytes,
    factura_num: str,
) -> None:
    host = (settings.SMTP_HOST or "").strip()
    port = int(settings.SMTP_PORT)
    from_addr = (settings.EMAILS_FROM_EMAIL or "").strip()
    if not host or not from_addr:
        raise RuntimeError("SMTP_HOST o EMAILS_FROM_EMAIL no configurados")

    user = (settings.SMTP_USER or "").strip()
    password = (settings.SMTP_PASSWORD or "").strip()

    msg = EmailMessage()
    fn = str(factura_num).strip() or "factura"
    msg["Subject"] = f"Factura {fn} · AB Logistics OS"
    msg["From"] = from_addr
    msg["To"] = to_email.strip()
    msg.set_content(
        "Adjuntamos su factura en PDF. Si no ve el mensaje con formato, utilice un cliente de correo compatible con HTML.\n",
        charset="utf-8",
    )
    msg.add_alternative(_invoice_smtp_html_simple(fn), subtype="html", charset="utf-8")

    safe = _safe_attachment_name_part(fn)
    msg.add_attachment(
        pdf_content,
        maintype="application",
        subtype="pdf",
        filename=f"Factura_{safe}.pdf",
    )

    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=60, context=ctx) as smtp:
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=60) as smtp:
            smtp.ehlo()
            if smtp.has_extn("starttls"):
                smtp.starttls(context=ctx)
                smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
    logger.info("Factura enviada por SMTP (num=%s → %s)", fn, to_email.strip())


class EmailService:
    """
    Envío de correo vía SMTP (facturación).

    Usa ``asyncio.to_thread`` + ``smtplib`` para no bloquear el event loop de FastAPI.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings if settings is not None else get_settings()

    @staticmethod
    def smtp_configured(settings: Settings | None = None) -> bool:
        s = settings if settings is not None else get_settings()
        return bool((s.SMTP_HOST or "").strip() and s.SMTP_PORT and (s.EMAILS_FROM_EMAIL or "").strip())

    async def send_invoice_email(self, to_email: str, pdf_content: bytes, factura_num: str) -> None:
        """
        Envía el PDF de factura por correo con plantilla HTML y adjunto ``Factura_[num].pdf``.

        Raises
        ------
        ValueError
            Destino inválido o PDF vacío.
        RuntimeError
            SMTP no configurado o error de envío no recuperable.
        """
        if not pdf_content:
            raise ValueError("PDF vacío")
        dest = _normalize_dest_email(to_email)
        if not dest:
            raise ValueError("Email de destino no válido")
        if not self.smtp_configured(self._settings):
            raise RuntimeError(
                "SMTP no configurado: defina SMTP_HOST, SMTP_PORT y EMAILS_FROM_EMAIL (o use EMAIL_FROM_ADDRESS como remitente)."
            )
        fn = str(factura_num).strip()
        try:
            await asyncio.to_thread(
                _send_invoice_smtp_sync,
                self._settings,
                dest,
                pdf_content,
                fn,
            )
        except Exception as exc:
            logger.exception("Fallo SMTP al enviar factura %s: %s", fn, exc)
            raise RuntimeError(f"No se pudo enviar el correo: {exc!s}") from exc


def send_onboarding_invite(dest_email: str, onboarding_link: str) -> bool:
    """Envía (o reenvía) invitación de onboarding por correo."""
    dest = _normalize_dest_email(dest_email)
    link = str(onboarding_link or "").strip()
    if not dest or not link:
        logger.info("email onboarding omitido: destino o enlace inválido")
        return False
    if not _resend_configured():
        logger.warning("Resend no configurado; no se envía invitación de onboarding")
        return False

    settings = get_settings()
    assert settings.RESEND_API_KEY and settings.EMAIL_FROM_ADDRESS
    resend.api_key = settings.RESEND_API_KEY

    try:
        resend.Emails.send(
            {
                "from": settings.EMAIL_FROM_ADDRESS,
                "to": [dest],
                "subject": "Invitación de onboarding · AB Logistics OS",
                "html": _onboarding_invite_html(link),
            }
        )
        logger.info("invitación onboarding enviada (email=%s)", dest)
        return True
    except Exception as exc:
        logger.exception("Fallo al enviar invitación de onboarding: %s", exc)
        return False
