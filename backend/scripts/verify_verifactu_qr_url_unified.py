#!/usr/bin/env python3
"""
Comprueba que la URL SREI sea única entre el builder canónico y ``generate_verifactu_qr_with_url``.

Uso desde la raíz del repo o `backend/`:
  python scripts/verify_verifactu_qr_url_unified.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permitir ejecutar sin instalar el paquete
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.core.verifactu_qr import generate_verifactu_qr_with_url  # noqa: E402
from app.services.aeat_qr_service import build_srei_verifactu_url  # noqa: E402


def main() -> int:
    inv = {
        "nif_emisor": "B12345678",
        "num_factura": "FAC-2026-000042",
        "fecha_emision": "2026-04-15",
        "importe_total": 250.0,
        "hash_registro": "cafebabe" * 8,
    }
    _, url_qr = generate_verifactu_qr_with_url(inv)
    url_canon = build_srei_verifactu_url(
        inv["nif_emisor"],
        inv["num_factura"],
        inv["fecha_emision"],
        float(inv["importe_total"]),
        huella_hash=inv["hash_registro"],
    )
    assert url_qr == url_canon, f"URLs difieren:\n  QR: {url_qr}\n  SREI: {url_canon}"
    assert "vlz/SREI/VERIFACTU" in url_qr
    assert "hc=cafebabe" in url_qr
    print("OK: preview/core SREI URL coincide con build_srei_verifactu_url")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
