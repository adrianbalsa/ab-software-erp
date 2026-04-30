"""Señales P1 para GO-live: Sentry + cadena VeriFactu + degradación Redis en rate limit.

No importar ``sentry_sdk`` a nivel de módulo: inicialización ocurre tras ``get_settings()`` en ``main``.
"""

from __future__ import annotations

import logging
import time
from typing import Any

_log = logging.getLogger(__name__)

_THROTTLE_MONO: dict[str, float] = {}
_RUNTIME_REDIS_THROTTLE_SEC = 300.0


def _throttle_allow(key: str, seconds: float) -> bool:
    now = time.monotonic()
    last = _THROTTLE_MONO.get(key, 0.0)
    if now - last < seconds:
        return False
    _THROTTLE_MONO[key] = now
    return True


def _sentry_capture_message(message: str, *, level: str, **scope_extras: Any) -> None:
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for k, v in scope_extras.items():
                if v is not None:
                    scope.set_extra(k, v)
            sentry_sdk.capture_message(message, level=level)
    except Exception:
        return


def notify_redis_shared_rate_limit_fatal(
    message: str,
    exc: BaseException | None,
    *,
    reason: str,
) -> None:
    """
    Antes de ``RuntimeError`` en arranque / configuración de rate limit compartido.
    Log + Sentry (fatal) para que el monitor sintético y el equipo vean la causa.
    """
    _log.critical("p1_redis_rate_limit_backend: %s reason=%s exc=%s", message, reason, exc)
    _sentry_capture_message(
        message,
        level="fatal",
        reason=reason,
        exc_type=type(exc).__name__ if exc else None,
        exc_msg=(str(exc)[:800] if exc else None),
    )


def notify_redis_rate_limit_runtime_degraded(exc: BaseException, *, channel: str) -> None:
    """
    Redis intermitente durante ``strategy.hit`` (fail-open). Una alerta cada
    ``_RUNTIME_REDIS_THROTTLE_SEC`` por canal para evitar tormenta.
    """
    key = f"rl_runtime:{channel}"
    if not _throttle_allow(key, _RUNTIME_REDIS_THROTTLE_SEC):
        return
    _log.error(
        "p1_redis_rate_limit_runtime_degraded channel=%s exc_type=%s exc=%s",
        channel,
        type(exc).__name__,
        exc,
    )
    _sentry_capture_message(
        f"Redis degraded during rate limit check ({channel})",
        level="error",
        channel=channel,
        exc_type=type(exc).__name__,
        exc_msg=str(exc)[:800],
    )


def notify_verifactu_chain_integrity_failure(
    *,
    empresa_id: str,
    source: str,
    error_code: str | None,
    summary: str,
) -> None:
    """Cadena rota o inválida (auditoría / verificar-cadena). Webhook ya puede existir; esto alimenta Sentry P1."""
    if not _throttle_allow(f"vf_chain:{empresa_id}", 120.0):
        return
    short = (summary or "").strip()[:1200]
    _log.error(
        "p1_verifactu_chain_integrity empresa_id=%s source=%s code=%s detail=%s",
        empresa_id,
        source,
        error_code,
        short[:400],
    )
    _sentry_capture_message(
        f"VeriFactu chain integrity failure ({source})",
        level="error",
        empresa_id=empresa_id,
        source=source,
        error_code=error_code,
        summary=short,
    )


async def check_sentry_p1_configuration() -> dict[str, Any]:
    """
    En **production** exige ``SENTRY_DSN`` configurado (sin exponer el valor).
    Otros entornos: skipped (no afecta a ``/health/deep`` en CI/desarrollo).
    """
    from app.core.config import get_settings
    from app.core.health_checks import _check_dict

    settings = get_settings()
    if bool(getattr(settings, "TESTING", False)):
        return _check_dict(ok=True, detail="sentry_check_skipped_testing", skipped=True)
    env = str(getattr(settings, "ENVIRONMENT", "") or "").strip().lower()
    if env != "production":
        return _check_dict(ok=True, detail="sentry_check_skipped_non_production", skipped=True)
    dsn = (settings.SENTRY_DSN or "").strip()
    if dsn:
        return _check_dict(ok=True, detail="sentry_dsn_configured", skipped=False)
    return _check_dict(
        ok=False,
        detail="sentry_dsn_missing_p1_production_requires_sentry",
        skipped=False,
    )
