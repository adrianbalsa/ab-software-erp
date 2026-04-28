#!/usr/bin/env python3
"""
Validación bloqueante de infraestructura para go-live.

Checks:
- API: HEAD sobre endpoints /health y cabeceras de seguridad.
- Base de datos: conectividad rápida a Supabase y Redis con latencia.
- Certificados: días restantes del certificado mTLS AEAT.
- Entorno: DEBUG=False y ENVIRONMENT=production.

Salida:
- 0: todos los checks OK (imprime "SISTEMA LISTO PARA GO-LIVE").
- 1: al menos un check falló (bloquea despliegue automático).
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from urllib.parse import urljoin


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


def _err(msg: str) -> None:
    print(f"ERROR {msg}", file=sys.stderr)


async def _check_environment() -> bool:
    from app.core.config import get_settings

    settings = get_settings()
    ok = True
    env = (settings.ENVIRONMENT or "").strip().lower()

    if env != "production":
        _err(f"ENVIRONMENT debe ser 'production' y es '{env or 'unset'}'")
        ok = False
    else:
        _ok("ENVIRONMENT=production")

    if settings.DEBUG:
        _err("DEBUG debe ser False en go-live")
        ok = False
    else:
        _ok("DEBUG=False")

    return ok


async def _check_api_security_headers() -> bool:
    import httpx

    base_url = (os.getenv("API_BASE_URL") or "").strip() or "http://127.0.0.1:8000"
    base = base_url.rstrip("/") + "/"
    endpoints = ("/health", "/health/deep")
    required_headers = ("strict-transport-security", "x-frame-options")
    ok = True

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for path in endpoints:
            url = urljoin(base, path.lstrip("/"))
            try:
                started = time.perf_counter()
                response = await client.head(url)
                if response.status_code == 405:
                    response = await client.get(url)
                latency_ms = (time.perf_counter() - started) * 1000.0
            except Exception as exc:  # noqa: BLE001
                _err(f"API {path} no accesible ({exc})")
                ok = False
                continue

            if response.status_code >= 500:
                _err(f"API {path} respondió {response.status_code}")
                ok = False
            else:
                _ok(f"API {path} accesible ({response.status_code}, {latency_ms:.1f} ms)")

            missing = [name for name in required_headers if name not in response.headers]
            if missing:
                _err(f"Cabeceras de seguridad ausentes en {path}: {', '.join(missing)}")
                ok = False
            else:
                _ok(f"Cabeceras de seguridad presentes en {path}")

    return ok


async def _check_supabase_latency() -> bool:
    import httpx

    from app.core.config import get_settings

    settings = get_settings()
    base = settings.SUPABASE_URL.rstrip("/")
    headers = {
        "apikey": settings.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
    }

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base}/rest/v1/", headers=headers)
    except Exception as exc:  # noqa: BLE001
        _err(f"Supabase no accesible ({exc})")
        return False
    latency_ms = (time.perf_counter() - started) * 1000.0
    if response.status_code >= 500:
        _err(f"Supabase respondió {response.status_code} ({latency_ms:.1f} ms)")
        return False
    _ok(f"Supabase OK ({response.status_code}, {latency_ms:.1f} ms)")
    return True


async def _check_redis_latency() -> bool:
    from app.core.config import get_settings

    settings = get_settings()
    redis_url = (settings.REDIS_URL or "").strip()
    if not redis_url:
        _err("REDIS_URL no configurado")
        return False

    try:
        from redis import asyncio as redis_asyncio
    except Exception as exc:  # noqa: BLE001
        _err(f"Cliente Redis no disponible ({exc})")
        return False

    started = time.perf_counter()
    try:
        client = redis_asyncio.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        try:
            await client.ping()
        finally:
            await client.aclose()
    except Exception as exc:  # noqa: BLE001
        _err(f"Redis no accesible ({exc})")
        return False
    latency_ms = (time.perf_counter() - started) * 1000.0
    _ok(f"Redis OK ({latency_ms:.1f} ms)")
    return True


async def _check_aeat_certificate() -> bool:
    from app.core.mtls_certificates import check_aeat_mtls_certificate_expiry

    result = await check_aeat_mtls_certificate_expiry(db=None)
    certificates = result.get("certificates") if isinstance(result, dict) else None
    if not isinstance(certificates, list) or not certificates:
        _err("No se pudo inspeccionar ningún certificado AEAT")
        return False

    ok = True
    for cert in certificates:
        if not isinstance(cert, dict):
            _err("Formato inesperado al leer certificado AEAT")
            ok = False
            continue
        source = str(cert.get("source") or "unknown")
        days_remaining = cert.get("days_remaining")
        detail = str(cert.get("detail") or "")
        cert_ok = bool(cert.get("ok"))
        if isinstance(days_remaining, int):
            print(f"INFO  Certificado AEAT [{source}] -> {days_remaining} días restantes")
        else:
            print(f"INFO  Certificado AEAT [{source}] -> días restantes no disponibles")
        if not cert_ok:
            _err(f"Certificado AEAT en alerta/fallo [{source}] ({detail})")
            ok = False

    return ok


async def _run() -> int:
    checks: list[tuple[str, bool]] = []

    try:
        checks.append(("environment", await _check_environment()))
    except Exception as exc:  # noqa: BLE001
        _err(f"Falló check de entorno ({exc})")
        checks.append(("environment", False))

    try:
        checks.append(("api_headers", await _check_api_security_headers()))
    except Exception as exc:  # noqa: BLE001
        _err(f"Falló check de API ({exc})")
        checks.append(("api_headers", False))

    try:
        checks.append(("supabase", await _check_supabase_latency()))
    except Exception as exc:  # noqa: BLE001
        _err(f"Falló check de Supabase ({exc})")
        checks.append(("supabase", False))

    try:
        checks.append(("redis", await _check_redis_latency()))
    except Exception as exc:  # noqa: BLE001
        _err(f"Falló check de Redis ({exc})")
        checks.append(("redis", False))

    try:
        checks.append(("aeat_certificate", await _check_aeat_certificate()))
    except Exception as exc:  # noqa: BLE001
        _err(f"Falló check de certificado AEAT ({exc})")
        checks.append(("aeat_certificate", False))

    failed = [name for name, status in checks if not status]
    if failed:
        _err(f"Checks fallidos: {', '.join(failed)}")
        return 1

    print("SISTEMA LISTO PARA GO-LIVE")
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
