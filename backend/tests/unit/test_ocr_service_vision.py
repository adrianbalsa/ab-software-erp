"""Tests de OCR por visión LLM (LiteLLM); sin Azure Document Intelligence."""

from __future__ import annotations

import pytest

from app.services.ocr_service import DocumentProcessorService, process_logistics_ticket
from app.services.secret_manager_service import reset_secret_manager


def test_vision_payload_to_gasto_dict_maps_ticket_fields() -> None:
    parsed = {
        "cif_emisor": "b12345678",
        "nombre_gasolinera": "Estación Demo",
        "fecha": "2024-06-01",
        "base_imponible": 10.0,
        "iva": 2.1,
        "total": 12.1,
        "litros_combustible": 25.5,
        "requires_review": False,
    }
    out = DocumentProcessorService.vision_payload_to_gasto_dict(parsed)
    assert out["nif_proveedor"] == "B12345678"
    assert out["proveedor"] == "ESTACIÓN DEMO"
    assert out["fecha"] == "2024-06-01"
    assert out["total"] == 12.1
    assert out["iva"] == 2.1
    assert out["base_imponible"] == 10.0
    assert out["litros_combustible"] == 25.5
    assert out["moneda"] == "EUR"
    assert "COMBUSTIBLE" in (out.get("concepto") or "")


@pytest.mark.asyncio
async def test_process_logistics_ticket_uses_litellm_acompletion(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_secret_manager()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-ocr-unit")
    monkeypatch.delenv("OCR_VISION_MODEL", raising=False)

    async def fake_acompletion(**kwargs: object) -> object:
        assert kwargs.get("model") == "openai/gpt-4o"
        assert kwargs.get("api_key") == "sk-test-ocr-unit"

        class _Msg:
            content = (
                '{"cif_emisor":"B00000000","nombre_gasolinera":"Shell Test",'
                '"fecha":"2024-01-15","base_imponible":10,"iva":2.1,"total":12.1,'
                '"litros_combustible":5,"requires_review":false}'
            )

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]
            usage = None

        return _Resp()

    import app.services.ocr_service as ocr_mod

    monkeypatch.setattr(ocr_mod.litellm, "acompletion", fake_acompletion)

    # JPEG magic bytes (contenido mínimo no vacío)
    image = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    out = await process_logistics_ticket(image)
    assert out["nombre_gasolinera"] == "Shell Test"
    assert out["total"] == 12.1
    assert out["requires_review"] is False

    reset_secret_manager()
