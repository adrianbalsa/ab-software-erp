from __future__ import annotations

import asyncio
import os
import traceback
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import get_settings

DISCORD_COLOR_CRITICAL = 0xED4245


def short_traceback_from_exc(exc: BaseException, *, limit_lines: int = 12) -> str:
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    lines = [ln.rstrip() for ln in tb.splitlines() if ln.strip()]
    return "\n".join(lines[:limit_lines])


class AlertService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._webhook_url = (os.getenv("DISCORD_WEBHOOK_URL") or "").strip()

    async def send_critical_alert(self, message: str, details: dict[str, Any] | None = None) -> None:
        if not self._webhook_url:
            return

        detail_lines = []
        for key, value in (details or {}).items():
            detail_lines.append(f"**{key}:** `{value}`")
        detail_text = "\n".join(detail_lines) if detail_lines else "No extra details."

        payload = {
            "embeds": [
                {
                    "title": "Critical System Failure",
                    "description": message[:3000],
                    "color": DISCORD_COLOR_CRITICAL,
                    "fields": [
                        {"name": "Environment", "value": self._settings.ENVIRONMENT, "inline": True},
                        {"name": "Timestamp (UTC)", "value": datetime.now(timezone.utc).isoformat(), "inline": True},
                        {"name": "Details", "value": detail_text[:1024], "inline": False},
                    ],
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                await client.post(self._webhook_url, json=payload)
        except Exception:
            # Never break API execution because alerting fails.
            return


alert_service = AlertService()


async def notify_critical_error(error_detail: str) -> None:
    await alert_service.send_critical_alert(
        message=error_detail or "Internal Server Error",
        details={"source": "backend", "severity": "critical"},
    )


def send_critical_alert(subject: str, body: str) -> dict[str, Any]:
    # Kept for scripts that still use a synchronous API.
    asyncio.run(
        alert_service.send_critical_alert(
            message=subject,
            details={"body": body},
        )
    )
    return {"provider": "discord_webhook", "status": "queued"}
