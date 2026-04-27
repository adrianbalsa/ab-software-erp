from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from typing import Any

import litellm
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError

from app.core.ai_observability import attach_ai_usage_to_span
from app.core.plans import CostMeter
from app.db.supabase import SupabaseAsync
from app.schemas.document_ai import DocumentExtraido, ProcessDocumentResponse
from app.services.ai_document_cache import cache_get_json, cache_set_json, ocr_cache_key
from app.services.secret_manager_service import get_secret_manager
from app.services.usage_quota_service import UsageQuotaService, estimate_ai_tokens
from app.services.vector_store import VectorStoreService

logger = logging.getLogger(__name__)

litellm.drop_params = True

_LOGISTICS_TICKET_JSON_SPEC = """
Devuelve ÚNICAMENTE un objeto JSON (sin markdown ni texto adicional) con estas claves exactas:
- "cif_emisor": string o null (CIF/NIF de la estación de servicio)
- "nombre_gasolinera": string o null
- "fecha": string en formato YYYY-MM-DD o null
- "base_imponible": número o null (EUR)
- "iva": número o null (cuota IVA en EUR)
- "total": número o null (total documento EUR)
- "litros_combustible": número o null (litros si constan)
- "requires_review": boolean — true si cualquier campo es ilegible, ambiguo, tapado o los importes no cuadran claramente; false si estás razonablemente seguro

Reglas:
- Si no ves un dato con claridad, usa null y pon requires_review en true.
- Los importes deben ser números decimales (punto como separador), sin símbolo €.
- La fecha debe ser la del ticket, no la de hoy, salvo que no sea legible (entonces null y requires_review true).
"""


class LogisticsTicketVisionModel(BaseModel):
    """Salida esperada del modelo de visión (ticket combustible)."""

    cif_emisor: str | None = None
    nombre_gasolinera: str | None = None
    fecha: str | None = None
    base_imponible: float | None = None
    iva: float | None = None
    total: float | None = None
    litros_combustible: float | None = None
    requires_review: bool = Field(default=False)


def _detect_image_mime(data: bytes) -> str:
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return "image/webp"
    return "image/jpeg"


def _resolve_vision_model() -> tuple[str, str | None]:
    """
    Retorna (modelo LiteLLM, api_key).
    Prioridad: OCR_VISION_MODEL explícito → OpenAI si hay clave → Gemini si hay clave.
    """
    mgr = get_secret_manager()
    custom = (os.getenv("OCR_VISION_MODEL") or "").strip()
    if custom:
        key = _litellm_api_key_for_model(custom)
        return custom, key
    if mgr.get_openai_api_key():
        return "openai/gpt-4o", mgr.get_openai_api_key()
    if mgr.get_google_gemini_api_key():
        gem = (os.getenv("OCR_GEMINI_MODEL") or "gemini/gemini-1.5-flash").strip()
        return gem, mgr.get_google_gemini_api_key()
    return "", None


def _litellm_api_key_for_model(model: str) -> str | None:
    ml = model.strip().lower()
    mgr = get_secret_manager()
    if ml.startswith("openai/") or ml.startswith("gpt-"):
        return mgr.get_openai_api_key()
    if "gemini" in ml:
        return mgr.get_google_gemini_api_key()
    return mgr.get_openai_api_key() or mgr.get_google_gemini_api_key()


def _parse_json_from_llm_text(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```\s*$", "", raw)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            raise
        obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("La respuesta del modelo no es un objeto JSON")
    return obj


class DocumentProcessorService:
    """
    OCR de tickets de combustible vía modelos de visión (OpenAI GPT-4o o Gemini) usando LiteLLM.
    La imagen se codifica en memoria (data URL); no se escribe a disco local.
    """

    def __init__(
        self,
        *,
        quota_service: UsageQuotaService | None = None,
        empresa_id: str | None = None,
    ) -> None:
        self._quota_service = quota_service
        self._empresa_id = str(empresa_id or "").strip() or None

    async def _consume_ocr_quota(self) -> None:
        if self._quota_service is None or not self._empresa_id:
            return
        await self._quota_service.consume(empresa_id=self._empresa_id, meter=CostMeter.OCR)

    async def process_logistics_ticket(self, image_bytes: bytes) -> dict[str, Any]:
        await self._consume_ocr_quota()
        return await process_logistics_ticket(image_bytes)

    @staticmethod
    def vision_payload_to_gasto_dict(parsed: dict[str, Any]) -> dict[str, Any]:
        """
        Convierte el JSON del modelo al dict histórico consumido por ``GastosService._dict_to_gasto_ocr_hint``.
        """
        try:
            m = LogisticsTicketVisionModel.model_validate(parsed)
        except ValidationError:
            m = LogisticsTicketVisionModel()

        nombre = (m.nombre_gasolinera or "").strip()
        cif = (m.cif_emisor or "").strip().upper()[:20] if m.cif_emisor else ""
        fecha_iso = (m.fecha or "").strip()[:10] if m.fecha else None
        if not fecha_iso:
            fecha_iso = None

        litros = m.litros_combustible
        concepto = "TICKET COMBUSTIBLE"
        if litros is not None and litros > 0:
            concepto = f"COMBUSTIBLE {litros:g} L"
        elif nombre:
            concepto = f"COMPRA EN {nombre.upper()[:80]}"

        prov_out = nombre.upper()[:100] if nombre else None
        nif_out = cif[:20] if cif else None

        total = m.total
        iva_v = m.iva
        base_v = m.base_imponible

        return {
            "fecha": fecha_iso,
            "proveedor": prov_out,
            "nif_proveedor": nif_out,
            "total": round(float(total), 2) if total is not None and total > 0 else None,
            "iva": round(float(iva_v), 2) if iva_v is not None and iva_v > 0 else None,
            "base_imponible": round(float(base_v), 2) if base_v is not None and base_v > 0 else None,
            "moneda": "EUR",
            "concepto": concepto.upper().strip()[:200] if concepto else None,
            "litros_combustible": float(litros) if litros is not None and litros > 0 else None,
            "ocr_confidence": None,
            "requires_manual_review": bool(m.requires_review),
        }


class OCRService(DocumentProcessorService):
    """
    Compatibilidad con ``GastosService``: delega en visión LLM (LiteLLM: GPT‑4o / Gemini).
    """

    async def analizar_ticket(self, archivo_bytes: bytes) -> dict[str, Any]:
        from app.core.math_engine import validate_logistics_ticket_amounts

        raw = await self.process_logistics_ticket(archivo_bytes)
        ok, _reason = validate_logistics_ticket_amounts(
            base_imponible=raw.get("base_imponible"),
            iva=raw.get("iva"),
            total=raw.get("total"),
        )
        if not ok:
            raw["requires_review"] = True
        merged = dict(raw)
        legacy = self.vision_payload_to_gasto_dict(merged)
        if not ok:
            legacy["requires_manual_review"] = True
        return legacy


async def process_logistics_ticket(image_bytes: bytes) -> dict[str, Any]:
    """
    Envía la imagen al modelo de visión y devuelve un dict JSON con los campos del ticket.

    Incluye ``requires_review`` (coherente con el contrato del modelo). La observabilidad
    usa Sentry ``op="ocr.vision"``, ``name="process_ticket"``.
    """
    if not image_bytes:
        raise HTTPException(status_code=422, detail="Imagen vacía")

    model, api_key = _resolve_vision_model()
    if not model or not api_key:
        logger.error("OCR visión: faltan OPENAI_API_KEY y GOOGLE_API_KEY/GEMINI_API_KEY")
        raise HTTPException(
            status_code=503,
            detail="OCR no configurado: defina OPENAI_API_KEY o GOOGLE_API_KEY (Gemini).",
        )

    mime = _detect_image_mime(image_bytes)
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": _LOGISTICS_TICKET_JSON_SPEC.strip()},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]

    try:
        import sentry_sdk
    except ImportError:
        sentry_sdk = None  # type: ignore[assignment]

    async def _call_vision() -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Eres un extractor experto de datos fiscales de tickets de gasolinera en España. "
                        "Sigues estrictamente el formato JSON pedido."
                    ),
                },
                {"role": "user", "content": user_content},
            ],
            "api_key": api_key,
            "temperature": 0.1,
            "max_tokens": 1200,
        }
        ml = model.lower()
        if ml.startswith("openai/") or ml.startswith("gpt-"):
            kwargs["response_format"] = {"type": "json_object"}

        response = await litellm.acompletion(**kwargs)
        try:
            import sentry_sdk

            attach_ai_usage_to_span(
                sentry_sdk.get_current_span(),
                getattr(response, "usage", None),
                model_id=model,
            )
        except Exception:
            pass
        text = ""
        choices = getattr(response, "choices", None) or []
        if choices:
            msg = getattr(choices[0], "message", None)
            if msg is not None:
                text = str(getattr(msg, "content", None) or "")

        parsed = _parse_json_from_llm_text(text)
        validated = LogisticsTicketVisionModel.model_validate(parsed)
        return validated.model_dump(mode="json")

    try:
        if sentry_sdk is not None:
            with sentry_sdk.start_span(op="ocr.vision", name="process_ticket"):
                return await _call_vision()
        return await _call_vision()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Fallo OCR visión (LiteLLM)")
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo analizar el ticket con el modelo de visión: {e!s}",
        ) from e


_VAMPIRE_DOCUMENT_JSON_SPEC = """
Analiza la imagen (ticket o factura de gasto logístico, p. ej. combustible) y responde SOLO con JSON válido
(sin markdown) con estas claves exactas:
- "proveedor_nombre": string o null
- "nif_proveedor": string o null
- "numero_documento": string o null
- "fecha_documento": string YYYY-MM-DD o null
- "base_imponible": número o null
- "iva": número o null
- "total": número o null
- "moneda": string 3 letras, p. ej. "EUR"
- "litros_combustible": número o null
- "tipo_documento": uno de "ticket_combustible", "factura", "otro"
- "ciudad_o_ubicacion": string o null (localidad si aparece)
- "requires_review": boolean — true si hay dudas o campos ilegibles

Importes como números decimales con punto; sin símbolo de moneda.
"""


def _resolve_vampire_ocr_model() -> tuple[str, str | None]:
    custom = (os.getenv("LITELLM_MODEL_OCR") or "").strip()
    if custom:
        return custom, _litellm_api_key_for_model(custom)
    mgr = get_secret_manager()
    if mgr.get_openai_api_key():
        return "openai/gpt-4o-mini", mgr.get_openai_api_key()
    return _resolve_vision_model()


def _embedding_model_name() -> str:
    return (os.getenv("LITELLM_EMBEDDING_MODEL") or "openai/text-embedding-3-small").strip()


async def _litellm_embed_text(*, text: str, api_key: str) -> list[float]:
    model = _embedding_model_name()
    try:
        import sentry_sdk
    except ImportError:
        sentry_sdk = None  # type: ignore[assignment]

    async def _run() -> list[float]:
        resp = await litellm.aembedding(model=model, input=text, api_key=api_key)
        try:
            import sentry_sdk

            usage = getattr(resp, "usage", None) or (resp.get("usage") if isinstance(resp, dict) else None)
            attach_ai_usage_to_span(sentry_sdk.get_current_span(), usage, model_id=model)
        except Exception:
            pass
        data = getattr(resp, "data", None) or (resp.get("data") if isinstance(resp, dict) else None)
        if not data:
            raise RuntimeError("Respuesta de embedding sin data")
        first = data[0]
        vec = getattr(first, "embedding", None) or (first.get("embedding") if isinstance(first, dict) else None)
        if not isinstance(vec, list) or len(vec) != 1536:
            raise RuntimeError(f"Embedding inválido o dimensión distinta de 1536 (len={len(vec) if isinstance(vec, list) else 'n/a'})")
        return [float(x) for x in vec]

    if sentry_sdk is not None:
        with sentry_sdk.start_span(op="ai.embedding", name="document_summary"):
            return await _run()
    return await _run()


async def _vampire_vision_extract(image_bytes: bytes) -> dict[str, Any]:
    if not image_bytes:
        raise HTTPException(status_code=422, detail="Imagen vacía")

    model, api_key = _resolve_vampire_ocr_model()
    if not model or not api_key:
        raise HTTPException(
            status_code=503,
            detail="Vampire Radar no configurado: defina OPENAI_API_KEY / GOOGLE_API_KEY o LITELLM_MODEL_OCR.",
        )

    mime = _detect_image_mime(image_bytes)
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"
    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": _VAMPIRE_DOCUMENT_JSON_SPEC.strip()},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]

    try:
        import sentry_sdk
    except ImportError:
        sentry_sdk = None  # type: ignore[assignment]

    async def _call() -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Eres un extractor fiscal experto para transporte y logística en España.",
                },
                {"role": "user", "content": user_content},
            ],
            "api_key": api_key,
            "temperature": 0.1,
            "max_tokens": 1600,
        }
        if model.lower().startswith("openai/") or model.lower().startswith("gpt-"):
            kwargs["response_format"] = {"type": "json_object"}
        response = await litellm.acompletion(**kwargs)
        try:
            import sentry_sdk

            attach_ai_usage_to_span(
                sentry_sdk.get_current_span(),
                getattr(response, "usage", None),
                model_id=model,
            )
        except Exception:
            pass
        text = ""
        choices = getattr(response, "choices", None) or []
        if choices:
            msg = getattr(choices[0], "message", None)
            if msg is not None:
                text = str(getattr(msg, "content", None) or "")
        parsed = _parse_json_from_llm_text(text)
        return DocumentExtraido.model_validate(parsed).model_dump(mode="json")

    try:
        if sentry_sdk is not None:
            with sentry_sdk.start_span(op="ai.vision", name="vampire_radar_extract"):
                return await _call()
        return await _call()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Vampire Radar: fallo visión LiteLLM")
        raise HTTPException(status_code=502, detail=f"Error extrayendo documento: {e!s}") from e


def _build_document_summary(doc: DocumentExtraido) -> str:
    parts = [
        f"Documento tipo {doc.tipo_documento}.",
        f"Proveedor: {doc.proveedor_nombre or 'desconocido'}.",
        f"NIF/CIF: {doc.nif_proveedor or 'N/D'}.",
        f"Número: {doc.numero_documento or 'N/D'}.",
        f"Fecha: {doc.fecha_documento or 'N/D'}.",
        f"Total {doc.moneda or 'EUR'}: {doc.total}.",
        f"Base: {doc.base_imponible}, IVA: {doc.iva}.",
    ]
    if doc.litros_combustible is not None:
        parts.append(f"Litros combustible: {doc.litros_combustible}.")
    if doc.ciudad_o_ubicacion:
        parts.append(f"Ubicación: {doc.ciudad_o_ubicacion}.")
    if doc.requires_review:
        parts.append("Requiere revisión humana.")
    return " ".join(str(p) for p in parts if p is not None)


async def vampire_radar_process_document(
    *,
    image_bytes: bytes,
    empresa_id: str,
    db: SupabaseAsync,
) -> ProcessDocumentResponse:
    """
    Vampire Radar: OCR estructurado, resumen, embedding e inserción en ``document_embeddings``.
    Caché Redis por hash SHA-256 del archivo (tenant-scoped).
    """
    eid = str(empresa_id or "").strip()
    if not eid:
        raise HTTPException(status_code=400, detail="empresa_id inválido")

    digest = hashlib.sha256(image_bytes).hexdigest()
    ck = ocr_cache_key(empresa_id=eid, file_sha256=digest)
    cached = await cache_get_json(ck)
    if cached:
        try:
            return ProcessDocumentResponse(
                document=DocumentExtraido.model_validate(cached.get("document") or {}),
                summary=str(cached.get("summary") or ""),
                embedding_id=cached.get("embedding_id"),
                cache_hit=True,
            )
        except Exception:
            pass

    quota = UsageQuotaService(db)
    await quota.consume(empresa_id=eid, meter=CostMeter.OCR)
    raw = await _vampire_vision_extract(image_bytes)
    doc = DocumentExtraido.model_validate(raw)
    summary = _build_document_summary(doc)

    mgr = get_secret_manager()
    openai_key = mgr.get_openai_api_key()
    embedding_id: str | None = None
    if openai_key:
        try:
            import sentry_sdk
        except ImportError:
            sentry_sdk = None  # type: ignore[assignment]

        try:
            await quota.consume(
                empresa_id=eid,
                meter=CostMeter.AI,
                units=estimate_ai_tokens(summary, minimum=500, output_reserve=0),
            )
            vec = await _litellm_embed_text(text=summary, api_key=openai_key)
            vs = VectorStoreService(db)
            meta: dict[str, Any] = {
                "source": "vampire_radar",
                "tipo_documento": doc.tipo_documento,
                "requires_review": doc.requires_review,
                "sha256": digest,
            }
            if sentry_sdk is not None:
                with sentry_sdk.start_span(op="ai.vector", name="insert_document_embedding") as ins_span:
                    embedding_id = await vs.insert_document_embedding(
                        empresa_id=eid,
                        content=summary,
                        metadata=meta,
                        embedding=vec,
                        source_sha256=digest,
                    )
                    ins_span.set_data("ai.embedding_row_id", embedding_id)
            else:
                embedding_id = await vs.insert_document_embedding(
                    empresa_id=eid,
                    content=summary,
                    metadata=meta,
                    embedding=vec,
                    source_sha256=digest,
                )
        except Exception as exc:
            logger.warning("Vampire Radar: no se pudo indexar embedding (se devuelve OCR igual): %s", exc)
    else:
        logger.warning("Vampire Radar: OPENAI_API_KEY ausente; se omite indexación vectorial")

    out = ProcessDocumentResponse(
        document=doc,
        summary=summary,
        embedding_id=embedding_id,
        cache_hit=False,
    )
    await cache_set_json(
        ck,
        {
            "document": doc.model_dump(mode="json"),
            "summary": summary,
            "embedding_id": embedding_id,
        },
    )
    return out
