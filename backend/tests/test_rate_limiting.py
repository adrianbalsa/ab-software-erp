"""Políticas de rate limiting (global, auth, fiscal y buckets costosos)."""

from __future__ import annotations

from app.core.rate_limit import expensive_endpoint_bucket, fiscal_aeat_submission_path


def test_fiscal_aeat_paths_match_verifactu_and_facturas() -> None:
    assert fiscal_aeat_submission_path("/api/v1/verifactu/retry-pending", "POST") is True
    assert fiscal_aeat_submission_path("/api/v1/verifactu/audit/qr-preview/1", "GET") is False
    assert fiscal_aeat_submission_path("/api/v1/facturas/42/finalizar", "POST") is True
    assert fiscal_aeat_submission_path("/api/v1/facturas/42/reenviar-aeat", "POST") is True
    assert fiscal_aeat_submission_path("/facturas/1/finalizar", "POST") is True
    assert fiscal_aeat_submission_path("/api/v1/facturas/1/finalizar", "GET") is False


def test_expensive_endpoint_bucket_matching() -> None:
    assert expensive_endpoint_bucket("/ai/chat", "POST") == "ai"
    assert expensive_endpoint_bucket("/api/v1/advisor/ask", "POST") == "ai"
    assert expensive_endpoint_bucket("/api/v1/chatbot/ask", "POST") == "ai"
    assert expensive_endpoint_bucket("/maps/distance", "GET") == "maps"
    assert expensive_endpoint_bucket("/api/v1/routes/optimize-route", "POST") == "maps"
    assert expensive_endpoint_bucket("/gastos/ocr", "POST") == "ocr"
    assert expensive_endpoint_bucket("/api/v1/gastos/logistics-ticket", "POST") == "ocr"
    assert expensive_endpoint_bucket("/api/v1/verifactu/retry-pending", "POST") is None
