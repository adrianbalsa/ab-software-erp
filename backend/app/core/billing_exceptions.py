"""Excepciones de negocio para cuotas y límites de facturación SaaS."""


class InvoiceMonthlyQuotaExceededError(Exception):
    """
    Se superó el máximo de facturas selladas (mes natural) del plan Compliance.

    El cliente HTTP debe mapear a 403 con ``detail`` que incluya ``code`` estable.
    """

    code: str = "invoice_monthly_quota_exceeded"

    def __init__(self, *, cap: int, used: int, message: str) -> None:
        self.cap = int(cap)
        self.used = int(used)
        super().__init__(message)
