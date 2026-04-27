#!/usr/bin/env python3
"""
Comprueba variables y rutas mínimas para un envío VeriFactu a **homologación** (sin llamar a la AEAT).

Uso (desde `backend/` con `.env` cargado como el resto de scripts):
  python scripts/check_aeat_homologacion_readiness.py
  python scripts/check_aeat_homologacion_readiness.py --strict

Salida: 0 si todo OK, 1 si hay advertencias, 2 si faltan requisitos bloqueantes para homologación.
Ver docs/operations/AEAT_VERIFACTU_HOMOLOGACION.md y GOLIVE Fase 3.1.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Misma carga de .env que config del proyecto
_ROOT = Path(__file__).resolve().parents[1]
if (_ROOT / ".env").is_file():
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=_ROOT / ".env")
    except ImportError:
        pass
if (_ROOT.parent / ".env").is_file():
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=_ROOT.parent / ".env")
    except ImportError:
        pass


def _warn(msg: str) -> None:
    print(f"WARN  {msg}", file=sys.stderr)


def _err(msg: str) -> None:
    print(f"ERROR {msg}", file=sys.stderr)


def _ok(msg: str) -> None:
    print(f"OK    {msg}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Prerrequisitos envío VeriFactu homologación AEAT (solo lectura local).")
    p.add_argument(
        "--strict",
        action="store_true",
        help="Trata advertencias (p. ej. XSD desactivado) como error (código 2).",
    )
    args = p.parse_args(argv)

    try:
        from app.core.config import get_settings
    except Exception as exc:  # noqa: BLE001
        _err(f"No se pudo cargar configuración: {exc}")
        return 2

    s = get_settings()
    exit_code = 0

    if not s.AEAT_VERIFACTU_ENABLED:
        _err("AEAT_VERIFACTU_ENABLED=false — activar para homologación.")
        return 2
    _ok("AEAT_VERIFACTU_ENABLED=true")

    if s.AEAT_VERIFACTU_USE_PRODUCTION:
        _err("AEAT_VERIFACTU_USE_PRODUCTION=true — para homologación debe ser false.")
        return 2
    _ok("AEAT_VERIFACTU_USE_PRODUCTION=false (homologación)")

    url_test = (s.AEAT_VERIFACTU_SUBMIT_URL_TEST or "").strip()
    if not url_test:
        _err("AEAT_VERIFACTU_SUBMIT_URL_TEST vacío — configurar endpoint de pruebas AEAT.")
        return 2
    _ok(f"AEAT_VERIFACTU_SUBMIT_URL_TEST definido ({len(url_test)} caracteres)")

    p12 = (s.AEAT_CLIENT_P12_PATH or "").strip()
    cert = (s.AEAT_CLIENT_CERT_PATH or "").strip()
    key = (s.AEAT_CLIENT_KEY_PATH or "").strip()
    if p12:
        path = Path(p12)
        if path.is_file():
            _ok(f"AEAT_CLIENT_P12_PATH existe: {path}")
        else:
            _warn(f"AEAT_CLIENT_P12_PATH no es fichero legible: {p12}")
            exit_code = max(exit_code, 1)
    elif cert and key:
        c_ok = Path(cert).is_file()
        k_ok = Path(key).is_file()
        if c_ok and k_ok:
            _ok("AEAT_CLIENT_CERT_PATH + AEAT_CLIENT_KEY_PATH existen")
        else:
            if not c_ok:
                _warn(f"AEAT_CLIENT_CERT_PATH no legible: {cert}")
            if not k_ok:
                _warn(f"AEAT_CLIENT_KEY_PATH no legible: {key}")
            exit_code = max(exit_code, 1)
    else:
        _err("Sin certificado mTLS: defina AEAT_CLIENT_P12_PATH o (AEAT_CLIENT_CERT_PATH + AEAT_CLIENT_KEY_PATH).")
        return 2

    if not s.AEAT_VERIFACTU_XSD_VALIDATE_REQUEST:
        _warn("AEAT_VERIFACTU_XSD_VALIDATE_REQUEST=false — recomendado true antes de homologación.")
        exit_code = max(exit_code, 1)
    else:
        _ok("AEAT_VERIFACTU_XSD_VALIDATE_REQUEST=true")

    if s.AEAT_BLOQUEAR_PROD_EN_DESARROLLO:
        _ok("AEAT_BLOQUEAR_PROD_EN_DESARROLLO=true (evita endpoint prod en dev)")
    else:
        _warn("AEAT_BLOQUEAR_PROD_EN_DESARROLLO=false — revisar en entornos no productivos.")

    wsdl = (s.AEAT_VERIFACTU_WSDL_URL or "").strip()
    if wsdl:
        _ok("AEAT_VERIFACTU_WSDL_URL definido")
    else:
        _warn("AEAT_VERIFACTU_WSDL_URL vacío — puede ser opcional según cliente SOAP; revisar.")

    if args.strict and exit_code > 0:
        return 2
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
