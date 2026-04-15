"""Políticas de rate limiting (global, auth, fiscal)."""

from __future__ import annotations

from app.core.rate_limit import fiscal_aeat_submission_path


def test_fiscal_aeat_paths_match_verifactu_and_facturas() -> None:
    assert fiscal_aeat_submission_path("/api/v1/verifactu/retry-pending", "POST") is True
    assert fiscal_aeat_submission_path("/api/v1/verifactu/audit/qr-preview/1", "GET") is False
    assert fiscal_aeat_submission_path("/api/v1/facturas/42/finalizar", "POST") is True
    assert fiscal_aeat_submission_path("/api/v1/facturas/42/reenviar-aeat", "POST") is True
    assert fiscal_aeat_submission_path("/facturas/1/finalizar", "POST") is True
    assert fiscal_aeat_submission_path("/api/v1/facturas/1/finalizar", "GET") is False
