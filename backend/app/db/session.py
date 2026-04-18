"""
Motor SQLAlchemy opcional (conexión directa a Postgres o a través de PgBouncer).

Si ``DATABASE_URL`` no está configurada (p. ej. solo Supabase HTTP), ``get_engine()`` devuelve ``None``.
En ``ENVIRONMENT=production``, ``app.core.config`` exige ``DATABASE_URL`` explícita no vacía
(``ConfigError`` al importar/arrancar); el motor SQLAlchemy es obligatorio para candados
transaccionales VeriFactu (``pg_advisory_xact_lock``) en multi-réplica.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def _connect_args_for_database_url(url: str) -> dict[str, Any]:
    """
    PgBouncer en ``pool_mode = transaction`` no mantiene sentencias preparadas entre asignaciones
    de conexión; con el driver psycopg3 conviene ``prepare_threshold=0`` (equivalente práctico
    a desactivar preparación agresiva). La URL puede incluir ``prepared_statements=false`` para
    drivers/herramientas que lo interpreten.
    """
    if "+psycopg" in url and "asyncpg" not in url:
        return {"prepare_threshold": 0}
    return {}


def get_engine() -> Engine | None:
    global _engine, SessionLocal
    settings = get_settings()
    if not settings.DATABASE_URL:
        return None
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            connect_args=_connect_args_for_database_url(settings.DATABASE_URL),
        )
        SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session] | None:
    """Factory de sesiones ORM; ``None`` si no hay ``DATABASE_URL``."""
    eng = get_engine()
    if eng is None:
        return None
    return SessionLocal
