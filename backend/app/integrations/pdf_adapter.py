from __future__ import annotations

import base64
from typing import Any

import anyio


def _load_pdf_generator() -> Any:
    """
    Carga el generador PDF desde el backend (migrado desde el legacy).
    """
    from app.services.pdf_service import generar_pdf_factura

    return generar_pdf_factura


async def generar_pdf_factura_base64(
    *,
    datos_empresa: dict[str, Any],
    datos_cliente: dict[str, Any],
    conceptos: list[dict[str, Any]],
) -> str:
    generar_pdf_factura = _load_pdf_generator()

    def _call() -> bytes:
        return generar_pdf_factura(datos_empresa, datos_cliente, conceptos)

    pdf_bytes = await anyio.to_thread.run_sync(_call)
    return base64.b64encode(pdf_bytes).decode("ascii")

