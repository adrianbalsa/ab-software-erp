from __future__ import annotations

import asyncio
import base64
import html
import logging
import re
import smtplib
import ssl
from collections.abc import Callable
from email.message import EmailMessage
from typing import Any

import resend

from app.core.config import Settings, get_settings
from app.core.i18n import get_translator, normalize_lang

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _sentry_capture_email_failure(
    operacion: str,
    *,
    exc: BaseException | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Visibilidad operativa si falla el envío tras delegar en segundo plano."""
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("component", "email_resend")
            scope.set_tag("email_operacion", operacion)
            if extra:
                scope.set_context("email", extra)
            if exc is not None:
                sentry_sdk.capture_exception(exc)
            else:
                sentry_sdk.capture_message(
                    f"Fallo envío correo (Resend), operación={operacion}",
                    level="error",
                )
    except Exception:
        pass


def send_email_background_task(operacion: str, enviar_sync: Callable[[], bool]) -> None:
    """
    Envoltorio **síncrono** para Resend (SDK bloqueante), pensado para ``BackgroundTasks.add_task``.

    Starlette/FastAPI ejecutan tareas síncronas en un hilo de trabajo tras enviar la respuesta HTTP,
    evitando bloquear el event loop con la latencia de red de Resend.
    """
    try:
        ok = enviar_sync()
    except Exception as exc:
        logger.exception("Fallo no controlado en envío de correo en segundo plano (%s)", operacion)
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
        return
    if not ok:
        logger.error("Envío de correo en segundo plano devolvió fallo (%s)", operacion)
        _sentry_capture_email_failure(
            operacion,
            exc=None,
            extra={"motivo": "enviar_sync_retorno_false"},
        )


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


def _invoice_html(factura_data: dict[str, Any], *, lang: str | None = None) -> str:
    t = get_translator(lang or factura_data.get("preferred_language"))
    lng = normalize_lang(lang or factura_data.get("preferred_language"))
    num = html.escape(str(factura_data.get("numero_factura") or "—"))
    fecha = html.escape(str(factura_data.get("fecha_emision") or "—"))
    total = factura_data.get("total_factura")
    base = factura_data.get("base_imponible")
    iva = factura_data.get("cuota_iva")
    emp = html.escape(str(factura_data.get("empresa_nombre") or "AB Logistics OS"))
    cli_plain = str(factura_data.get("cliente_nombre") or "Cliente")
    greeting = html.escape(t("Hello {name},").format(name=cli_plain))

    def fmt_eur(v: Any) -> str:
        try:
            return f"{float(v):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        except (TypeError, ValueError):
            return "—"

    return f"""<!DOCTYPE html>
<html lang="{lng}">
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width"/></head>
<body style="margin:0;padding:0;background-color:#18181b;font-family:system-ui,-apple-system,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#18181b;padding:24px 12px;">
    <tr><td align="center">
      <table width="600" style="max-width:600px;background:#27272a;border-radius:12px;overflow:hidden;border:1px solid #3f3f46;">
        <tr>
          <td style="padding:24px 28px;background:linear-gradient(135deg,#27272a 0%,#14532d 100%);border-bottom:1px solid #3f3f46;">
            <p style="margin:0;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#a1a1aa;">AB Logistics OS</p>
            <h1 style="margin:8px 0 0;font-size:20px;font-weight:700;color:#fafafa;">{html.escape(t("New invoice issued"))}</h1>
            <p style="margin:8px 0 0;font-size:14px;color:#d4d4d8;">{emp}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:24px 28px;color:#e4e4e7;font-size:15px;line-height:1.6;">
            <p style="margin:0 0 16px;">{greeting}</p>
            <p style="margin:0 0 20px;">{html.escape(t("We attach your invoice PDF with VeriFactu fingerprint."))}</p>
            <table width="100%" style="border-collapse:collapse;font-size:14px;">
              <tr><td style="padding:8px 0;color:#a1a1aa;">{html.escape(t("Number"))}</td><td align="right" style="padding:8px 0;color:#fafafa;font-weight:600;">{num}</td></tr>
              <tr><td style="padding:8px 0;color:#a1a1aa;">{html.escape(t("Date"))}</td><td align="right" style="padding:8px 0;color:#fafafa;">{fecha}</td></tr>
              <tr><td style="padding:8px 0;color:#a1a1aa;">{html.escape(t("Taxable base"))}</td><td align="right" style="padding:8px 0;">{fmt_eur(base)}</td></tr>
              <tr><td style="padding:8px 0;color:#a1a1aa;">{html.escape(t("VAT"))}</td><td align="right" style="padding:8px 0;">{fmt_eur(iva)}</td></tr>
              <tr><td colspan="2" style="border-top:1px solid #3f3f46;padding-top:12px;"></td></tr>
              <tr><td style="padding:8px 0;color:#6ee7b7;font-weight:600;">{html.escape(t("Total"))}</td><td align="right" style="padding:8px 0;color:#6ee7b7;font-size:18px;font-weight:700;">{fmt_eur(total)}</td></tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 28px;background:#1f1f23;font-size:12px;color:#71717a;border-top:1px solid #3f3f46;">
            {html.escape(t("Automatically generated message. Do not reply to this email."))}
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _quota_html(empresa_email: str, current_count: int, limit: int, *, lang: str | None = None) -> str:
    t = get_translator(lang)
    lng = normalize_lang(lang)
    em = html.escape(empresa_email)
    return f"""<!DOCTYPE html>
<html lang="{lng}"><head><meta charset="utf-8"/></head>
<body style="margin:0;padding:0;background-color:#18181b;font-family:system-ui,sans-serif;">
  <table width="100%" style="background:#18181b;padding:24px;"><tr><td align="center">
    <table width="560" style="max-width:560px;background:#27272a;border-radius:12px;border:1px solid #3f3f46;">
      <tr><td style="padding:24px 28px;background:linear-gradient(135deg,#27272a,#14532d);">
        <h1 style="margin:0;font-size:18px;color:#fafafa;">{html.escape(t("Fleet quota alert"))}</h1>
        <p style="margin:8px 0 0;font-size:13px;color:#a1a1aa;">{em}</p>
      </td></tr>
      <tr><td style="padding:24px;color:#e4e4e7;font-size:14px;line-height:1.6;">
        <p>{html.escape(t("You have reached {current} of {limit} vehicles allowed on your plan.")).format(current=current_count, limit=limit)}</p>
        <p style="margin:16px 0 0;color:#a1a1aa;font-size:13px;">{html.escape(t("Upgrade your plan to keep operating without interruptions."))}</p>
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""


def _onboarding_invite_html(onboarding_link: str, *, lang: str | None = None) -> str:
    t = get_translator(lang)
    lng = normalize_lang(lang)
    safe_link = str(onboarding_link or "").strip()
    return f"""<!DOCTYPE html>
<html lang="{lng}"><head><meta charset="utf-8"/></head>
<body style="margin:0;padding:0;background-color:#18181b;font-family:system-ui,sans-serif;">
  <table width="100%" style="background:#18181b;padding:24px;"><tr><td align="center">
    <table width="560" style="max-width:560px;background:#27272a;border-radius:12px;border:1px solid #3f3f46;">
      <tr><td style="padding:24px 28px;background:linear-gradient(135deg,#27272a,#14532d);">
        <h1 style="margin:0;font-size:20px;color:#fafafa;">{html.escape(t("Onboarding invitation"))}</h1>
        <p style="margin:8px 0 0;font-size:13px;color:#a1a1aa;">AB Logistics OS</p>
      </td></tr>
      <tr><td style="padding:24px;color:#e4e4e7;font-size:14px;line-height:1.6;">
        <p>{html.escape(t("We have resent your invitation to complete onboarding."))}</p>
        <p style="margin:18px 0;">
          <a href="{html.escape(safe_link, quote=True)}" style="display:inline-block;background:#16a34a;color:#ffffff;text-decoration:none;padding:10px 16px;border-radius:8px;font-weight:600;">
            {html.escape(t("Continue onboarding"))}
          </a>
        </p>
        <p style="margin:0;color:#a1a1aa;font-size:12px;word-break:break-all;">{html.escape(t("If the button does not work, copy this link into your browser: {link}").format(link=safe_link))}</p>
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""


def send_invoice_email_from_base64(
    factura_data: dict[str, Any],
    pdf_base64: str | None,
    dest_email: str | None,
    lang: str | None = None,
) -> bool:
    """
    Decodifica ``pdf_base64`` y delega en ``send_invoice_email`` (Resend, síncrono).

    Tras ``POST /facturas/desde-portes`` debe invocarse vía ``send_email_background_task`` dentro de
    ``BackgroundTasks`` para no bloquear la respuesta HTTP ni el event loop.
    """
    if not pdf_base64 or not dest_email:
        return False
    try:
        pdf_bytes = base64.b64decode(pdf_base64.encode("ascii"))
    except Exception as exc:
        logger.warning("No se pudo decodificar PDF base64 para email: %s", exc)
        return False
    return send_invoice_email(factura_data, pdf_bytes, dest_email, lang=lang)


def send_invoice_email(
    factura_data: dict[str, Any],
    pdf_content: bytes,
    dest_email: str,
    *,
    lang: str | None = None,
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

    eff_lang = lang or factura_data.get("preferred_language")
    t = get_translator(eff_lang)

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
            "subject": t("Invoice {num} · AB Logistics OS").format(num=num),
            "html": _invoice_html(factura_data, lang=eff_lang),
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


def send_quota_alert(
    empresa_email: str, current_count: int, limit: int, *, lang: str | None = None
) -> bool:
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
    t = get_translator(lang)

    try:
        resend.Emails.send(
            {
                "from": settings.EMAIL_FROM_ADDRESS,
                "to": [dest],
                "subject": t("Alert: {current}/{limit} vehicles · AB Logistics OS").format(
                    current=current_count, limit=limit
                ),
                "html": _quota_html(dest, current_count, limit, lang=lang),
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


def _invoice_smtp_html_simple(factura_num: str, *, lang: str | None = None) -> str:
    """HTML sin incrustar nombre de fichero duplicado (evita doble escape en plantilla)."""
    t = get_translator(lang)
    lng = normalize_lang(lang)
    num = html.escape(str(factura_num).strip() or "—")
    return f"""<!DOCTYPE html>
<html lang="{lng}">
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f4f5;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" style="max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;
        box-shadow:0 4px 24px rgba(15,23,42,0.08);border:1px solid #e4e4e7;">
        <tr>
          <td style="padding:28px 32px;background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);">
            <p style="margin:0;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:#94a3b8;">
              {html.escape(t("Fiscal document"))}
            </p>
            <h1 style="margin:10px 0 0;font-size:22px;font-weight:700;color:#f8fafc;line-height:1.25;">
              {html.escape(t("Your invoice is ready"))}
            </h1>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px;color:#3f3f46;font-size:15px;line-height:1.65;">
            <p style="margin:0 0 16px;">{html.escape(t("Dear customer,"))}</p>
            <p style="margin:0 0 20px;">
              {html.escape(t("We attach the PDF invoice {num}, issued under applicable e-invoicing rules (VeriFactu / SIF).").format(num=str(factura_num).strip() or "—"))}
            </p>
            <p style="margin:0;font-size:13px;color:#71717a;">
              {html.escape(t("Attachment filename: Factura_{name}.pdf").format(name=_safe_attachment_name_part(factura_num)))}
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:20px 32px;background:#fafafa;border-top:1px solid #e4e4e7;font-size:12px;color:#71717a;">
            {html.escape(t("Automatically generated message. Contact your account manager for questions about the document."))}
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
    *,
    lang: str | None = None,
) -> None:
    host = (settings.SMTP_HOST or "").strip()
    port = int(settings.SMTP_PORT)
    from_addr = (settings.EMAILS_FROM_EMAIL or "").strip()
    if not host or not from_addr:
        raise RuntimeError("SMTP_HOST o EMAILS_FROM_EMAIL no configurados")

    user = (settings.SMTP_USER or "").strip()
    password = (settings.SMTP_PASSWORD or "").strip()

    t = get_translator(lang)
    msg = EmailMessage()
    fn = str(factura_num).strip() or "factura"
    msg["Subject"] = t("Invoice {num} · AB Logistics OS").format(num=fn)
    msg["From"] = from_addr
    msg["To"] = to_email.strip()
    msg.set_content(
        t(
            "We attach your invoice in PDF. If you do not see formatting, use an HTML-capable mail client."
        )
        + "\n",
        charset="utf-8",
    )
    msg.add_alternative(_invoice_smtp_html_simple(fn, lang=lang), subtype="html", charset="utf-8")

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

    async def send_invoice_email(
        self, to_email: str, pdf_content: bytes, factura_num: str, *, lang: str | None = None
    ) -> None:
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
                lang=lang,
            )
        except Exception as exc:
            logger.exception("Fallo SMTP al enviar factura %s: %s", fn, exc)
            raise RuntimeError(f"No se pudo enviar el correo: {exc!s}") from exc


def send_onboarding_invite(dest_email: str, onboarding_link: str, *, lang: str | None = None) -> bool:
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
    t = get_translator(lang)

    try:
        resend.Emails.send(
            {
                "from": settings.EMAIL_FROM_ADDRESS,
                "to": [dest],
                "subject": t("Invitation to onboarding · AB Logistics OS"),
                "html": _onboarding_invite_html(link, lang=lang),
            }
        )
        logger.info("invitación onboarding enviada (email=%s)", dest)
        return True
    except Exception as exc:
        logger.exception("Fallo al enviar invitación de onboarding: %s", exc)
        return False
