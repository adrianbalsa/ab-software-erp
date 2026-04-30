"""
Golden vectors VeriFactu (AEAT): ``CanonicalHashService`` determinista.

Referencia: cadena UTF-8 = NIF + NúmeroSerie + Fecha(YYYY-MM-DD) + Importe(2 dec, punto) + HuellaAnterior (64 hex mayúsc.),
luego SHA-256 hex en MAYÚSCULAS.
"""

from __future__ import annotations

import hashlib
import sys
from decimal import Decimal
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.fiscal_logic import fiscal_amount_string_two_decimals
from app.core.verifactu_hashing import CanonicalHashService


NULL_CHAIN_64 = "0" * 64

# Caso B: payload fijo verificado frente a SHA-256 manual (openssl / hashlib).
_GOLDEN_B_NIF = "B12345678"
_GOLDEN_B_NUM = "VF-GOLD-000001"
_GOLDEN_B_FECHA = "2026-01-15"
_GOLDEN_B_IMPORTE_STR = "2.69"  # Decimal("2.685") → ROUND_HALF_UP a céntimo
_GOLDEN_B_PAYLOAD = (
    f"{_GOLDEN_B_NIF}{_GOLDEN_B_NUM}{_GOLDEN_B_FECHA}{_GOLDEN_B_IMPORTE_STR}{NULL_CHAIN_64}"
)
_GOLDEN_B_SHA256_HEX = hashlib.sha256(_GOLDEN_B_PAYLOAD.encode("utf-8")).hexdigest().upper()


def _assert_sha256_verifactu_format(digest: str) -> None:
    assert len(digest) == 64, "Huella VeriFactu: 256 bits = 64 hex"
    assert digest == digest.upper(), "AEAT: hex en mayúsculas"
    allowed = set("0123456789ABCDEF")
    assert all(c in allowed for c in digest), "Solo caracteres hexadecimales"


def test_case_a_normalizacion_nif_espacios_y_minusculas() -> None:
    """Caso A: NIF con espacios y minúsculas → misma huella que NIF canónico."""
    messy_nif = "  b12345678 \t"
    clean_nif = "B12345678"
    num = "FAC-2026-000042"
    fecha = "2026-04-28"
    total = Decimal("121.00")
    h_messy = CanonicalHashService.generate_verifactu_hash(
        messy_nif, num, fecha, total, NULL_CHAIN_64
    )
    h_clean = CanonicalHashService.generate_verifactu_hash(
        clean_nif, num, fecha, total, NULL_CHAIN_64
    )
    assert h_messy == h_clean
    _assert_sha256_verifactu_format(h_messy)
    # Cadena efectiva (referencia AEAT)
    prev_norm = NULL_CHAIN_64.upper()
    imp = fiscal_amount_string_two_decimals(total)
    expected_payload = f"{clean_nif}{num}{fecha}{imp}{prev_norm}"
    assert (
        hashlib.sha256(expected_payload.encode("utf-8")).hexdigest().upper() == h_messy
    )


def test_case_b_redondeo_critico_2_685_y_sha256_golden() -> None:
    """Caso B: 2.685 € → string ``2.69``; SHA-256 idéntico al cálculo manual explícito."""
    assert fiscal_amount_string_two_decimals(Decimal("2.685")) == _GOLDEN_B_IMPORTE_STR
    got = CanonicalHashService.generate_verifactu_hash(
        _GOLDEN_B_NIF,
        _GOLDEN_B_NUM,
        _GOLDEN_B_FECHA,
        Decimal("2.685"),
        NULL_CHAIN_64,
    )
    assert got == _GOLDEN_B_SHA256_HEX
    manual = hashlib.sha256(_GOLDEN_B_PAYLOAD.encode("utf-8")).hexdigest().upper()
    assert got == manual
    _assert_sha256_verifactu_format(got)


def test_case_c_eslabon_cero_64_ceros_primera_factura() -> None:
    """Caso C: huella anterior = 64 ceros (cadena nula estándar); hash válido AEAT."""
    nif = "B87654321"
    num = "SERIE-2026-000001"
    fecha = "2026-03-01"
    total = Decimal("50.00")
    h = CanonicalHashService.generate_verifactu_hash(nif, num, fecha, total, NULL_CHAIN_64)
    _assert_sha256_verifactu_format(h)
    assert h != NULL_CHAIN_64
    prev_norm = NULL_CHAIN_64.upper()
    imp = fiscal_amount_string_two_decimals(total)
    assert (
        hashlib.sha256(f"{nif}{num}{fecha}{imp}{prev_norm}".encode("utf-8")).hexdigest().upper()
        == h
    )


def test_case_d_encadenamiento_tres_facturas_integridad() -> None:
    """Caso D: h(N) depende de h(N-1); alterar el eslabón rompe la huella."""
    nif = "B11111111"
    fecha = "2026-06-15"
    h1 = CanonicalHashService.generate_verifactu_hash(
        nif, "F-2026-000001", fecha, Decimal("100.00"), NULL_CHAIN_64
    )
    h2 = CanonicalHashService.generate_verifactu_hash(
        nif, "F-2026-000002", fecha, Decimal("200.00"), h1
    )
    h3 = CanonicalHashService.generate_verifactu_hash(
        nif, "F-2026-000003", fecha, Decimal("300.00"), h2
    )
    for hx in (h1, h2, h3):
        _assert_sha256_verifactu_format(hx)
    assert h1 != h2 != h3
    # Si el tercer registro usara cadena nula en lugar del hash real de la factura 2:
    h3_wrong_prev = CanonicalHashService.generate_verifactu_hash(
        nif, "F-2026-000003", fecha, Decimal("300.00"), NULL_CHAIN_64
    )
    assert h3 != h3_wrong_prev
    # Reproducibilidad: mismo eslabón → mismo h3
    h3_bis = CanonicalHashService.generate_verifactu_hash(
        nif, "F-2026-000003", fecha, Decimal("300.00"), h2
    )
    assert h3_bis == h3


def test_anti_regression_float_importe_typeerror() -> None:
    """No se admite ``float`` en importe (deriva IEEE); ``TypeError`` explícita."""
    with pytest.raises(TypeError, match="float"):
        CanonicalHashService.generate_verifactu_hash(
            "B12345678",
            "X-1",
            "2026-01-01",
            1.005,  # type: ignore[arg-type]
            NULL_CHAIN_64,
        )


def test_formato_digest_64_hex_mayusculas_en_cadena_completa() -> None:
    """Integridad de formato en varios vectores."""
    vectors = [
        CanonicalHashService.generate_verifactu_hash(
            "B22222222", "A-1", "2026-12-31", Decimal("0.01"), NULL_CHAIN_64
        ),
        _GOLDEN_B_SHA256_HEX,
    ]
    for d in vectors:
        _assert_sha256_verifactu_format(d)
