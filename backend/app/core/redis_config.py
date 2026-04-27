from __future__ import annotations

import os
from urllib.parse import urlparse

from arq.connections import RedisSettings

from app.core.config import get_settings

DEFAULT_ARQ_QUEUE_NAME = "arq:queue"


def billing_queue_name() -> str:
    """Nombre de cola compartido por API y worker de facturacion."""
    return (os.getenv("ARQ_BILLING_QUEUE_NAME") or DEFAULT_ARQ_QUEUE_NAME).strip() or DEFAULT_ARQ_QUEUE_NAME


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _sentinel_hosts(raw: str) -> list[tuple[str, int]]:
    hosts: list[tuple[str, int]] = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        host, sep, port_raw = item.partition(":")
        if not host:
            continue
        port = int(port_raw) if sep and port_raw else 26379
        hosts.append((host, port))
    if not hosts:
        raise RuntimeError("REDIS_SENTINEL_HOSTS no contiene hosts validos")
    return hosts


def redis_settings_from_env(*, purpose: str) -> RedisSettings:
    settings = get_settings()
    url = (settings.REDIS_URL or "").strip()
    if not url:
        raise RuntimeError(f"REDIS_URL es obligatoria para {purpose}")

    conn_timeout = _env_int("REDIS_CONN_TIMEOUT_SECONDS", 2)
    conn_retries = _env_int("REDIS_CONN_RETRIES", 5)
    conn_retry_delay = _env_int("REDIS_CONN_RETRY_DELAY_SECONDS", 1)
    max_connections_raw = (os.getenv("REDIS_MAX_CONNECTIONS") or "").strip()
    max_connections = int(max_connections_raw) if max_connections_raw else None

    sentinel_hosts_raw = (os.getenv("REDIS_SENTINEL_HOSTS") or "").strip()
    if sentinel_hosts_raw:
        parsed = urlparse(url)
        return RedisSettings(
            host=_sentinel_hosts(sentinel_hosts_raw),
            database=int((parsed.path or "/0").lstrip("/") or "0"),
            username=parsed.username,
            password=parsed.password,
            ssl=parsed.scheme == "rediss",
            conn_timeout=conn_timeout,
            conn_retries=conn_retries,
            conn_retry_delay=conn_retry_delay,
            max_connections=max_connections,
            sentinel=True,
            sentinel_master=(os.getenv("REDIS_SENTINEL_MASTER") or "mymaster").strip() or "mymaster",
            retry_on_timeout=True,
        )

    redis_settings = RedisSettings.from_dsn(url)
    redis_settings.conn_timeout = conn_timeout
    redis_settings.conn_retries = conn_retries
    redis_settings.conn_retry_delay = conn_retry_delay
    redis_settings.max_connections = max_connections
    redis_settings.retry_on_timeout = True
    return redis_settings
