"""
Comprobaciones de salud proactivas (latencia DB) y registro en ``infra_health_logs``.

Los mensajes de error se sanitizan para no exponer cadenas de conexión ni contraseñas.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Literal

from sqlalchemy import text

from app.db.session import get_engine

logger = logging.getLogger("infra_health_logs")

HealthOverall = Literal["healthy", "degraded", "fail", "skipped"]


def sanitize_error_message(msg: str) -> str:
    """
    Elimina patrones típicos de credenciales en URIs y literales password=.
    No sustituye el análisis humano; reduce fugas accidentales en logs.
    """
    if not msg:
        return ""
    s = str(msg)
    # postgresql://user:secret@host -> postgresql://user:***@host
    s = re.sub(
        r"((?:postgresql|postgres)://[^\s/:]+:)([^\s@]+)(@)",
        r"\1***\3",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"(mysql://[^\s/:]+:)([^\s@]+)(@)",
        r"\1***\3",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"(password=)([^\s&]+)", r"\1***", s, flags=re.IGNORECASE)
    s = re.sub(r"(PGPASSWORD\s*=\s*)(\S+)", r"\1***", s, flags=re.IGNORECASE)
    # Trunca mensajes enormes
    if len(s) > 4000:
        s = s[:3997] + "..."
    return s


def log_slow_http_request(*, latency_ms: float, path: str, method: str) -> None:
    """Registro explícito de petición lenta (middleware > 5 s)."""
    _insert_infra_health_log(
        source="api_latency",
        status="slow_request",
        latency_ms=latency_ms,
        message="request_exceeded_5s",
        path=path[:2000],
        method=method,
    )


def _insert_infra_health_log(
    *,
    source: str,
    status: str,
    latency_ms: float | None,
    message: str | None,
    path: str | None = None,
    method: str | None = None,
) -> None:
    """Inserta en ``infra_health_logs``; fallos de escritura no deben tumbar el health check."""
    eng = get_engine()
    if eng is None:
        logger.warning(
            "infra_health_logs: omitido insert (sin DATABASE_URL): source=%s status=%s",
            source,
            status,
        )
        return
    safe_msg = sanitize_error_message(message or "")
    try:
        with eng.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO public.infra_health_logs
                      (source, status, latency_ms, message, path, method)
                    VALUES
                      (:source, :status, :latency_ms, :message, :path, :method)
                    """
                ),
                {
                    "source": source,
                    "status": status,
                    "latency_ms": latency_ms,
                    "message": safe_msg or None,
                    "path": path,
                    "method": method,
                },
            )
    except Exception as exc:
        logger.warning(
            "infra_health_logs: insert fallido: %s",
            sanitize_error_message(str(exc)),
        )


def _db_check_with_timing() -> dict[str, Any]:
    """
    Ejecuta ``SELECT 1`` y clasifica por latencia (segundos reales).
    - < 0.5 s: healthy
    - 0.5–2 s: degraded (+ log tabla)
    - > 2 s o excepción: fail (+ log tabla)
    """
    eng = get_engine()
    if eng is None:
        return {
            "configured": False,
            "status": "skipped",
            "latency_ms": None,
            "detail": "DATABASE_URL not configured",
        }

    t0 = time.perf_counter()
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        elapsed = time.perf_counter() - t0
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        raw = str(exc)
        safe = sanitize_error_message(raw)
        _insert_infra_health_log(
            source="db_health",
            status="fail",
            latency_ms=round(elapsed * 1000, 3),
            message=safe,
        )
        return {
            "configured": True,
            "status": "fail",
            "latency_ms": round(elapsed * 1000, 3),
            "detail": safe,
        }

    ms = round(elapsed * 1000, 3)
    if elapsed < 0.5:
        return {
            "configured": True,
            "status": "healthy",
            "latency_ms": ms,
            "detail": "select_1_ok",
        }
    if elapsed <= 2.0:
        _insert_infra_health_log(
            source="db_health",
            status="degraded",
            latency_ms=ms,
            message="select_1_slow_threshold_500ms_2s",
        )
        return {
            "configured": True,
            "status": "degraded",
            "latency_ms": ms,
            "detail": "select_1_slow",
        }

    _insert_infra_health_log(
        source="db_health",
        status="fail",
        latency_ms=ms,
        message="select_1_exceeded_2s",
    )
    return {
        "configured": True,
        "status": "fail",
        "latency_ms": ms,
        "detail": "select_1_too_slow",
    }


async def perform_full_health_check() -> dict[str, Any]:
    """
    Salud completa centrada en la capa SQLAlchemy/Postgres.

    Estado global ``status``:
    - ``skipped``: sin ``DATABASE_URL`` (200 en endpoint; no 503).
    - ``healthy`` / ``degraded`` / ``fail``: según latencia o error de ``SELECT 1``.
    """
    db_result = await asyncio.to_thread(_db_check_with_timing)

    if not db_result.get("configured"):
        return {
            "status": "skipped",
            "database": db_result,
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    overall: HealthOverall = db_result["status"]  # type: ignore[assignment]

    return {
        "status": overall,
        "database": db_result,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
