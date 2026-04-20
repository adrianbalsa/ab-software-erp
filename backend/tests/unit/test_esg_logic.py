"""Tests ESG: factor ISO 14083, helpers y certificado PDF (ReportLab)."""

from __future__ import annotations

import hashlib

from app.core.constants import ISO_14083_DIESEL_CO2_KG_PER_LITRE, ISO_14083_REFERENCE_LABEL
from app.core.esg_engine import esg_certificate_co2_vs_euro_iii
from app.services.bi_service import _co2_kg_for_row
from app.services.esg_service import (
    diesel_co2eq_kg_from_litres,
    generate_porte_certificate_pdf_reportlab,
    sum_portal_esg_co2_ahorro_kg,
)
from app.services.esg_audit_service import certificate_content_sha256_hex, public_esg_verify_url
from app.services.pdf_esg_service import EsgPorteCertificatePdfModel


def test_public_esg_verify_url_default_origin() -> None:
    u = public_esg_verify_url(api_origin=None, verification_code="00000000-0000-4000-8000-000000000001")
    assert u.startswith("https://api.ablogistics.io/v1/public/verify-esg/")
    assert u.endswith("00000000-0000-4000-8000-000000000001")


def test_certificate_content_sha256_hex_matches_hashlib() -> None:
    b = b"%PDF-1.4 test"
    assert certificate_content_sha256_hex(b) == hashlib.sha256(b).hexdigest()


def test_iso14083_constant_is_267() -> None:
    assert ISO_14083_DIESEL_CO2_KG_PER_LITRE == 2.67
    assert "14083" in ISO_14083_REFERENCE_LABEL


def test_diesel_co2_from_litres() -> None:
    from pytest import approx

    assert diesel_co2eq_kg_from_litres(100.0) == approx(267.0)
    assert diesel_co2eq_kg_from_litres(0.0) == 0.0


def test_bi_co2_fallback_aligns_with_euro_vi_km_engine() -> None:
    row = {"km_estimados": 100.0, "km_reales": None, "co2_kg": None, "co2_emitido": None}
    from app.core.esg_engine import calculate_co2_emissions

    assert _co2_kg_for_row(row) == calculate_co2_emissions(100.0, "Euro VI")


def test_certificate_pdf_bytes_non_empty() -> None:
    model = EsgPorteCertificatePdfModel(
        certificate_id="ABL-ESG-TEST-00000000",
        content_fingerprint_sha256="a" * 64,
        empresa_nombre="Empresa Test SA",
        empresa_nif="B12345678",
        porte_id="00000000-0000-4000-8000-000000000001",
        fecha="2026-04-19",
        origen="Madrid",
        destino="Barcelona",
        km_estimados=620.0,
        km_reales=615.0,
        real_distance_km=618.0,
        km_vacio=40.0,
        engine_class="EURO_VI",
        fuel_type="DIESEL",
        vehiculo_label="1234 ABC · Tractor",
        normativa_euro="Euro VI",
        glec_gco2_km_full=800.0,
        glec_gco2_km_empty=550.0,
        co2_total_kg=123.456789,
        euro_iii_baseline_kg=200.0,
        ahorro_kg=76.543211,
        nox_total_kg=0.4,
        subcontratado=False,
        scope_note="Scope 1 — prueba unitaria.",
    )
    pdf = generate_porte_certificate_pdf_reportlab(model)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1500


def test_csv_row_co2_matches_esg_certificate_helper() -> None:
    """Misma función de certificación que CSV backend (esg_certificate_co2_vs_euro_iii)."""
    cert = esg_certificate_co2_vs_euro_iii(
        km_estimados=100.0,
        km_vacio=10.0,
        engine_class="EURO_VI",
        fuel_type="DIESEL",
        subcontratado=False,
    )
    assert cert["actual_total_kg"] > 0
    assert cert["euro_iii_baseline_kg"] >= cert["actual_total_kg"]


def test_portal_ytd_ahorro_sum_matches_certificate_triplet() -> None:
    from pytest import approx

    rows = [
        {
            "vehiculo_id": "11111111-1111-4111-8111-111111111111",
            "km_estimados": 100.0,
            "km_vacio": 10.0,
            "subcontratado": False,
        }
    ]
    flota = {
        "11111111-1111-4111-8111-111111111111": {"engine_class": "EURO_VI", "fuel_type": "DIESEL"},
    }
    cert = esg_certificate_co2_vs_euro_iii(
        km_estimados=100.0,
        km_vacio=10.0,
        engine_class="EURO_VI",
        fuel_type="DIESEL",
        subcontratado=False,
    )
    assert sum_portal_esg_co2_ahorro_kg(rows, flota) == approx(cert["ahorro_kg"], rel=1e-9)
