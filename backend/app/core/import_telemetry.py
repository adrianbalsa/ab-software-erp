"""Telemetría operativa de importaciones (sin PII de filas)."""

from __future__ import annotations

import logging
from typing import Any

from starlette.requests import Request

_log = logging.getLogger(__name__)


def log_import_event(
    request: Request | None,
    event: str,
    *,
    empresa_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Evento de producto para soporte y auditoría operativa.

    No registrar contenido de CSV, matrículas ni importes por fila.
    """
    rid = None
    if request is not None:
        rid = getattr(request.state, "request_id", None)
    payload: dict[str, Any] = {
        "event": event,
        "request_id": rid,
        "empresa_id": empresa_id,
    }
    if extra:
        payload.update(extra)
    _log.info("import_telemetry %s", payload)
