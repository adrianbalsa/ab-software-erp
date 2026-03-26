"""Observabilidad de errores críticos (webhook externo).

Diseñado para SLA B2B: enviar alertas asíncronas ante errores 5xx críticos
sin bloquear el request del cliente.
"""

from __future__ import annotations

import asyncio
import os
import time
import traceback
from typing import Any

import httpx
from fastapi import Request

from app.core.config import get_settings
from app.core.security import decode_access_token_payload

ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL") or ""

_THROTTLE_SECONDS = 60


class AlertManager:
  """Envío asíncrono de alertas críticas (Telegram/Discord vía webhook)."""

  def __init__(self) -> None:
    self._webhook_url = ALERT_WEBHOOK_URL
    # Throttle básico para evitar tormentas de alertas durante caídas.
    self._last_sent_by_key: dict[str, float] = {}

  async def send_critical_error(self, *, request: Request, error_detail: str) -> None:
    """
    Envia alerta 5xx a `ALERT_WEBHOOK_URL` (Telegram/Discord o equivalente).
    No lanza excepciones (failsafe).
    """
    url = self._webhook_url
    if not url:
      return

    endpoint = request.url.path
    tenant_id = _extract_tenant_id_from_request(request)

    key = f"{tenant_id or 'unknown'}:{endpoint}"
    now = time.time()
    last = self._last_sent_by_key.get(key) or 0.0
    if now - last < _THROTTLE_SECONDS:
      return
    self._last_sent_by_key[key] = now

    msg = format_critical_error_message(
      tenant_id=tenant_id,
      endpoint=endpoint,
      error_detail=error_detail,
    )

    # Payload compatible con webhooks típicos (Telegram: text; Discord: content).
    payload: dict[str, Any] = {"text": msg, "content": msg}
    try:
      async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        await client.post(url, json=payload)
    except Exception:
      # Nunca romper el request por fallos de notificación.
      return


_alert_manager = AlertManager()


def _extract_tenant_id_from_request(request: Request) -> str | None:
  auth = request.headers.get("authorization") or ""
  if not auth.lower().startswith("bearer "):
    return None
  token = auth.split(" ", 1)[1].strip()
  if not token:
    return None
  try:
    payload: dict[str, Any] = decode_access_token_payload(token)
    eid = payload.get("empresa_id")
    if eid is None:
      return None
    s = str(eid).strip()
    return s or None
  except Exception:
    return None


def format_critical_error_message(
  *,
  tenant_id: str | None,
  endpoint: str,
  error_detail: str,
) -> str:
  settings = get_settings()
  env = settings.ENVIRONMENT
  t = tenant_id or "unknown"
  short = (error_detail or "").strip()
  if not short:
    short = "Internal Server Error"

  # Formato solicitado en SLA: texto enriquecido para móvil.
  return "\n".join(
    [
      f"🚨 ERROR CRÍTICO - {env}",
      f"Endpoint: {endpoint}",
      f"Tenant_ID: {t}",
      f"Error: {short}",
    ]
  )


def short_traceback_from_exc(exc: BaseException, *, limit_lines: int = 12) -> str:
  tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
  lines = [ln.rstrip() for ln in tb.splitlines() if ln.strip()]
  # Primeras líneas contienen el mensaje + stack inicial.
  return "\n".join(lines[:limit_lines])


def schedule_critical_error_alert(*, request: Request, error_detail: str) -> None:
  """Planifica el envío sin bloquear."""
  asyncio.create_task(_alert_manager.send_critical_error(request=request, error_detail=error_detail))

