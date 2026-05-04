from __future__ import annotations

from fastapi import HTTPException, status

from app.core.billing_exceptions import InvoiceMonthlyQuotaExceededError


def test_invoice_monthly_quota_exception_stable_code() -> None:
    e = InvoiceMonthlyQuotaExceededError(cap=150, used=150, message="Límite alcanzado")
    assert InvoiceMonthlyQuotaExceededError.code == "invoice_monthly_quota_exceeded"
    assert e.cap == 150
    assert e.used == 150
    assert "Límite" in str(e)


def test_invoice_monthly_quota_maps_to_403_detail() -> None:
    """Misma forma que ``app.api.routes.facturas._invoice_monthly_quota_http``."""
    exc = InvoiceMonthlyQuotaExceededError(cap=150, used=150, message="Cuota mensual")
    http = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": InvoiceMonthlyQuotaExceededError.code,
            "cap": exc.cap,
            "used": exc.used,
            "message": str(exc),
        },
    )
    assert http.status_code == 403
    assert isinstance(http.detail, dict)
    assert http.detail["code"] == "invoice_monthly_quota_exceeded"
    assert http.detail["cap"] == 150
    assert http.detail["used"] == 150
