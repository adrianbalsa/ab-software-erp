from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import get_settings

_log = logging.getLogger(__name__)

_LEVEL_COLORS: dict[str, int] = {
    "INFO": 0x3B82F6,
    "WARNING": 0xF59E0B,
    "CRITICAL": 0xEF4444,
}


def _safe_context(context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(context, dict):
        return {}
    return context


def _build_markdown_message(
    *,
    title: str,
    message: str,
    level: str,
    environment: str,
    tenant_id: str | None,
    timestamp: str,
    context: dict[str, Any],
) -> str:
    context_block = ""
    if context:
        rendered = "\n".join(f"- **{k}**: `{v}`" for k, v in context.items())
        context_block = f"\n\n**Contexto**\n{rendered}"
    return (
        f"## {level} - {title}\n\n"
        f"{message}\n\n"
        f"**Entorno:** `{environment}`\n"
        f"**Tenant ID:** `{tenant_id or 'n/a'}`\n"
        f"**Timestamp (UTC):** `{timestamp}`"
        f"{context_block}"
    )


async def send_alert(
    title: str,
    message: str,
    level: str = "INFO",
    context: dict[str, Any] | None = None,
) -> None:
    settings = get_settings()
    webhook_url = (settings.ALERT_WEBHOOK_URL or "").strip()
    if not webhook_url:
        return

    normalized_level = (level or "INFO").strip().upper()
    timestamp = datetime.now(timezone.utc).isoformat()
    ctx = _safe_context(context)
    tenant_id = str(ctx.get("tenant_id") or "").strip() or None
    markdown_message = _build_markdown_message(
        title=title.strip() or "Platform Alert",
        message=message.strip() or "No detail provided.",
        level=normalized_level,
        environment=settings.ENVIRONMENT,
        tenant_id=tenant_id,
        timestamp=timestamp,
        context=ctx,
    )
    color = _LEVEL_COLORS.get(normalized_level, _LEVEL_COLORS["INFO"])
    payload = {
        # Slack incoming webhook.
        "text": markdown_message,
        # Discord compatibility.
        "content": markdown_message,
        "embeds": [
            {
                "title": f"{normalized_level} - {title}",
                "description": message,
                "color": color,
                "fields": [
                    {"name": "Entorno", "value": settings.ENVIRONMENT, "inline": True},
                    {"name": "Tenant ID", "value": tenant_id or "n/a", "inline": True},
                    {"name": "Timestamp (UTC)", "value": timestamp, "inline": False},
                ],
            }
        ],
        # Telegram Bot API compatibility (when chat_id is in webhook URL).
        "parse_mode": "Markdown",
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0)) as client:
            await client.post(webhook_url, json=payload)
    except Exception as exc:
        _log.warning("notification_service webhook failed: %s", exc)
