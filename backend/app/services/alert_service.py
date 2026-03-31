from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _build_text(subject: str, body: str) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    environment = _env("ALERT_ENVIRONMENT", "Production") or "Production"
    audit_logs_url = _env(
        "ALERT_AUDIT_LOGS_URL",
        "https://app.ablogistics-os.com/dashboard/admin/audit-logs",
    )
    return (
        f"[SENTINEL ALERT]\n"
        f"Subject: {subject}\n"
        f"Timestamp: {ts}\n"
        f"Environment: {environment}\n"
        f"Audit Logs: {audit_logs_url}\n\n"
        f"{body.strip()}\n"
    )


def _send_resend(
    *,
    api_key: str,
    sender: str,
    recipients: list[str],
    subject: str,
    text: str,
) -> dict[str, Any]:
    payload = {
        "from": sender,
        "to": recipients,
        "subject": subject,
        "text": text,
    }
    with httpx.Client(timeout=20.0) as client:
        r = client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    r.raise_for_status()
    return {"provider": "resend", "status_code": r.status_code, "response": r.json()}


def _send_sendgrid(
    *,
    api_key: str,
    sender: str,
    recipients: list[str],
    subject: str,
    text: str,
) -> dict[str, Any]:
    payload = {
        "personalizations": [{"to": [{"email": rcpt} for rcpt in recipients]}],
        "from": {"email": sender},
        "subject": subject,
        "content": [{"type": "text/plain", "value": text}],
    }
    with httpx.Client(timeout=20.0) as client:
        r = client.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    r.raise_for_status()
    return {"provider": "sendgrid", "status_code": r.status_code, "response": r.text}


def send_critical_alert(subject: str, body: str) -> dict[str, Any]:
    sender = _env("ALERT_EMAIL_FROM")
    recipients_raw = _env("ALERT_EMAIL_TO")
    recipients = [x.strip() for x in recipients_raw.split(",") if x.strip()]
    if not sender or not recipients:
        raise RuntimeError("ALERT_EMAIL_FROM / ALERT_EMAIL_TO no configurados")

    text = _build_text(subject=subject, body=body)

    resend_key = _env("RESEND_API_KEY")
    if resend_key:
        return _send_resend(
            api_key=resend_key,
            sender=sender,
            recipients=recipients,
            subject=subject,
            text=text,
        )

    sendgrid_key = _env("SENDGRID_API_KEY")
    if sendgrid_key:
        return _send_sendgrid(
            api_key=sendgrid_key,
            sender=sender,
            recipients=recipients,
            subject=subject,
            text=text,
        )

    raise RuntimeError("No hay proveedor de email configurado (RESEND_API_KEY o SENDGRID_API_KEY)")
