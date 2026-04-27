#!/usr/bin/env python3
"""
Comprueba aspectos de **Fase 3.2** (CORS/hosts/Redis TLS) leyendo la misma config que la API.

No valida DNS ni certificados en red. Ejecutar desde `backend/` con `.env` de producción o staging.

  PYTHONPATH=. python scripts/check_deploy_infra_readiness.py
  PYTHONPATH=. python scripts/check_deploy_infra_readiness.py --strict

Salida: 0 OK, 1 advertencias, 2 error (solo en --strict las advertencias pasan a 2).

Ver: docs/operations/DEPLOY_FINAL_TLS_CHECKLIST.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for dot in (_ROOT / ".env", _ROOT.parent / ".env"):
    if dot.is_file():
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=dot)
        except ImportError:
            break


def _ok(msg: str) -> None:
    print(f"OK    {msg}")


def _warn(msg: str) -> None:
    print(f"WARN  {msg}", file=sys.stderr)


def _err(msg: str) -> None:
    print(f"ERROR {msg}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fase 3.2: CORS, ALLOWED_HOSTS, REDIS TLS (solo lectura config).")
    p.add_argument(
        "--strict",
        action="store_true",
        help="Falla si REDIS_URL no usa rediss:// en producción con Redis configurado.",
    )
    args = p.parse_args(argv)

    try:
        from app.core.config import get_settings
    except Exception as exc:  # noqa: BLE001
        _err(f"No se pudo cargar configuración: {exc}")
        return 2

    s = get_settings()
    code = 0

    env = (s.ENVIRONMENT or "").strip().lower()
    _ok(f"ENVIRONMENT={env!r}")

    if "*" in s.ALLOWED_HOSTS:
        _warn(f"ALLOWED_HOSTS contiene '*': {s.ALLOWED_HOSTS!r}")
        code = max(code, 1)
    else:
        _ok(f"ALLOWED_HOSTS sin wildcard ({len(s.ALLOWED_HOSTS)} entradas)")

    if not s.CORS_ALLOW_ORIGINS:
        _err("CORS_ALLOW_ORIGINS vacío")
        return 2
    _ok(f"CORS_ALLOW_ORIGINS: {len(s.CORS_ALLOW_ORIGINS)} origen(es)")

    insecure_cors = [o for o in s.CORS_ALLOW_ORIGINS if o.startswith("http://")]
    if insecure_cors and env == "production":
        _warn(f"Orígenes CORS http:// en producción: {insecure_cors[:5]}")
        code = max(code, 1)

    redis_url = (s.REDIS_URL or "").strip()
    if not redis_url:
        _warn("REDIS_URL vacío — rate limit / ARQ pueden no ser válidos en este entorno.")
        code = max(code, 1)
    else:
        if redis_url.lower().startswith("rediss://"):
            _ok("REDIS_URL usa esquema rediss:// (TLS)")
        else:
            msg = "REDIS_URL no usa rediss:// — en producción use TLS (Railway Redis, ElastiCache TLS, etc.)."
            if env == "production":
                _warn(msg)
                code = max(code, 1)
            else:
                _ok(f"REDIS_URL definido ({redis_url.split('://', 1)[0]}://…)")

    if s.DEBUG and env == "production":
        _err("DEBUG no puede ser True en producción (config lo rechaza; si ves esto, revisar Settings).")
        return 2

    # --strict solo endurece salida en producción (evita fallar en entornos dev sin Redis/TLS).
    if args.strict and env == "production" and code > 0:
        return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
