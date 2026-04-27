#!/usr/bin/env python3
"""
Sonda HTTP opcional para readiness de API (go-live).

Uso: `docs/operations/GOLIVE_READINESS_CHECKLIST.md` (Fase 3.3),
`docs/operations/MONITORING_OBSERVABILITY.md`.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Iterable
from urllib.parse import urljoin

EXPECTED = (
    ("/live", (200,)),
    ("/ready", (200,)),
    ("/health/deep", (200, 503)),
)


def _print_expected() -> None:
    print("Rutas de salud esperadas en la API (sin autenticacion):")
    for path, codes in EXPECTED:
        print(f"  GET {path} -> HTTP {codes}")
    print()
    print("Ejecutar con --base-url para comprobar una URL real.")
    print("Opciones: --strict  |  --summarize-deep (requiere --base-url)")


def _print_deep_summary(payload: str) -> None:
    try:
        data: dict[str, Any] = json.loads(payload)
    except json.JSONDecodeError as exc:
        print(f"  deep: JSON no parseable ({exc})", file=sys.stderr)
        return
    status = data.get("status")
    print(f"  deep.status={status!r}")
    checks = data.get("checks")
    if not isinstance(checks, dict):
        return
    for name in sorted(checks.keys()):
        c = checks[name]
        if not isinstance(c, dict):
            print(f"  deep.checks.{name}=?")
            continue
        ok = c.get("ok")
        skipped = c.get("skipped")
        detail = str(c.get("detail") or "")[:120]
        tail = f" detail={detail!r}" if detail else ""
        print(f"  deep.checks.{name}: ok={ok} skipped={skipped}{tail}")


def _check_base(url: str, *, strict: bool, summarize_deep: bool) -> int:
    try:
        import httpx
    except ImportError:
        print("httpx no instalado; instala dependencias del backend (pip install -r requirements.txt).", file=sys.stderr)
        return 2

    base = url.rstrip("/") + "/"
    exit_code = 0
    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        for path, acceptable in EXPECTED:
            full = urljoin(base, path.lstrip("/"))
            try:
                r = client.get(full)
            except httpx.RequestError as exc:
                msg = f"ERROR {path}: {exc}"
                print(msg, file=sys.stderr)
                exit_code = 2 if strict else 0
                continue
            expected = (200,) if strict else acceptable
            if r.status_code not in expected:
                print(
                    f"WARN {path}: status {r.status_code} (esperado {expected})",
                    file=sys.stderr,
                )
                exit_code = 1 if strict else 0
            else:
                print(f"OK   {path}: {r.status_code}")
            if summarize_deep and path == "/health/deep" and r.content:
                try:
                    text = r.content.decode("utf-8")
                except UnicodeDecodeError:
                    text = ""
                if text:
                    _print_deep_summary(text)
    return exit_code


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Comprobacion HTTP opcional go-live (salud API).")
    p.add_argument(
        "--base-url",
        default=None,
        help="Origen HTTPS de la API (ej. https://api.ejemplo.com), sin barra final.",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exige HTTP 200 en /live, /ready y /health/deep; falla ante red o 503 en deep.",
    )
    p.add_argument(
        "--summarize-deep",
        action="store_true",
        help="Tras GET /health/deep, imprime resumen JSON (status y checks) para logs/evidencia.",
    )
    args = p.parse_args(list(argv) if argv is not None else None)

    if not args.base_url:
        _print_expected()
        if args.summarize_deep:
            print(
                "--summarize-deep requiere --base-url",
                file=sys.stderr,
            )
            return 2
        return 0

    return _check_base(
        args.base_url,
        strict=bool(args.strict),
        summarize_deep=bool(args.summarize_deep),
    )


if __name__ == "__main__":
    raise SystemExit(main())
