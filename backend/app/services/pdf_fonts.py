"""
Registro de fuentes TTF para PDFs (Roboto / Roboto Mono — aspecto tecnológico y legible).

Coloca los archivos en ``backend/assets/fonts/`` (ver descarga desde Google Fonts).
Si faltan, se usa Helvetica/Courier (core PDF) sin acentos problemáticos en algunos casos.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fpdf import FPDF

logger = logging.getLogger(__name__)

# backend/assets/fonts (no confundir con app/)
_ASSETS = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"


def register_brand_fonts(pdf: FPDF) -> tuple[str, str]:
    """
    Registra Roboto (texto) y RobotoMono (código / hash).

    Returns:
        (body_family, mono_family) nombres para ``set_font``.
    """
    reg = _ASSETS / "Roboto-Regular.ttf"
    bold = _ASSETS / "Roboto-Bold.ttf"
    # Variable font oficial (google/fonts ofl/robotomono); más fiable que enlaces legacy rotos.
    mono = _ASSETS / "RobotoMono-VF.ttf"

    if reg.is_file() and bold.is_file():
        try:
            pdf.add_font("Roboto", "", str(reg))
            pdf.add_font("Roboto", "B", str(bold))
            body = "Roboto"
        except Exception as exc:
            logger.warning("No se pudo cargar Roboto: %s", exc)
            body = "helvetica"
    else:
        logger.warning(
            "Fuentes de marca no encontradas en %s; usando Helvetica/Courier.",
            _ASSETS,
        )
        body = "helvetica"

    if mono.is_file():
        try:
            pdf.add_font("RobotoMono", "", str(mono))
            mono_f = "RobotoMono"
        except Exception as exc:
            logger.warning("No se pudo cargar RobotoMono: %s", exc)
            mono_f = "courier"
    else:
        mono_f = "courier"

    return body, mono_f
