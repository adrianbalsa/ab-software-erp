"""Errores internos del cliente VeriFactu / AEAT (SOAP, Zeep, validación XSD)."""

from __future__ import annotations

from typing import Any


class VeriFactuException(Exception):
    """
    Error homogéneo para fallos SOAP/XSD/Zeep en el envío AEAT.

    La API HTTP puede mapear ``code`` y ``http_status`` a respuestas JSON coherentes.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        fault_code: str | None = None,
        fault_string: str | None = None,
        detail: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.fault_code = fault_code
        self.fault_string = fault_string
        self.detail = detail
