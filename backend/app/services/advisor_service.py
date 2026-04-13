"""
LogisAdvisor: contexto agregado (finanzas, CIP, tesorería, cumplimiento) + LLM.

Usa **LiteLLM** (`litellm.acompletion`) para soportar varios proveedores vía variables de entorno.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import litellm

from app.core.verifactu import verify_invoice_chain
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.services.audit_logs_service import AuditLogsService
from app.services.finance_service import FinanceService
from app.services.portes_service import PortesService

litellm.drop_params = True

logger = logging.getLogger(__name__)

LOGIS_ADVISOR_SYSTEM_PROMPT = (
    "Eres LogisAdvisor, un consultor experto en economía logística y fiscalidad española. "
    "Tu objetivo es analizar datos del ERP AB Logistics OS. "
    "Tus respuestas deben ser quirúrgicas, basadas en datos reales del contexto y orientadas a "
    "maximizar el EBITDA y el cumplimiento VeriFactu. "
    "Si detectas anomalías en los hashes o en el CO₂, adviértelo proactivamente.\n\n"
    "**Matriz CIP y flota**\n"
    "- En la matriz CIP (Contribución / Intensidad de emisiones), una ruta con **margen neto bajo o negativo** "
    "y **alta huella de CO₂ relativa** actúa como **“vampiro”** de rentabilidad: consume margen y empeora el ratio CO₂/€.\n"
    "- Un **camión Euro III** (o normativa antigua) asignado a esas rutas suele amplificar el problema: mayor intensidad "
    "de emisiones por t·km y coste oculto en combustible/mantenimiento.\n"
    "- Recomienda **renovación hacia Euro VI** u homologación superior alineada con el **módulo ESG** y reducción de CO₂ "
    "por t·km, citando siempre las cifras del contexto JSON cuando existan.\n\n"
    "**Formato**: Markdown breve; no inventes cifras fuera del contexto. No expongas datos bancarios ni credenciales."
)


def _redact_leaks(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"\bES\d{22}\b", "[IBAN oculto]", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsk-[A-Za-z0-9]{16,}\b", "[clave oculta]", text)
    return text


def primary_model() -> str:
    """Modelo principal (formato LiteLLM, p. ej. ``openai/gpt-4o``)."""
    m = (os.getenv("ADVISOR_MODEL") or os.getenv("ADVISOR_LLM_MODEL") or "").strip()
    if m:
        return m
    legacy = (os.getenv("OPENAI_MODEL") or "").strip()
    if legacy:
        if "/" in legacy:
            return legacy
        return f"openai/{legacy}"
    return "openai/gpt-4o"


def fallback_model() -> str:
    return (os.getenv("ADVISOR_FALLBACK_MODEL") or "anthropic/claude-3-5-sonnet-20240620").strip()


def _model_chain() -> list[str]:
    primary = primary_model()
    fb = fallback_model()
    out = [primary]
    if fb and fb not in out:
        out.append(fb)
    return out


def model_name() -> str:
    """Compatibilidad: nombre del modelo primario configurado."""
    return primary_model()


def advisor_llm_configured() -> bool:
    """
    True si existen credenciales típicas para los proveedores por defecto (OpenAI y/o Anthropic).
    Ajusta las claves según el prefijo de ``ADVISOR_MODEL`` en despliegues avanzados.
    """
    if (os.getenv("OPENAI_API_KEY") or "").strip():
        return True
    if (os.getenv("ANTHROPIC_API_KEY") or "").strip():
        return True
    if (os.getenv("AZURE_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY") or "").strip():
        return True
    if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip():
        return True
    return False


def openai_configured() -> bool:
    """Alias histórico: el asistente usa LiteLLM; requiere credenciales de algún proveedor."""
    return advisor_llm_configured()


def _usage_to_dict(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        try:
            return usage.model_dump()
        except Exception:
            pass
    if isinstance(usage, dict):
        return dict(usage)
    return {"repr": repr(usage)}


def _completion_text(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    c0 = choices[0]
    msg = getattr(c0, "message", None)
    if msg is not None:
        return str(getattr(msg, "content", None) or "")
    return ""


def _response_model_id(response: Any, requested: str) -> str:
    mid = getattr(response, "model", None)
    if isinstance(mid, str) and mid.strip():
        return mid.strip()
    return requested


def _delta_from_chunk(chunk: Any) -> str:
    try:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            return ""
        c0 = choices[0]
        delta = getattr(c0, "delta", None)
        if delta is None:
            return ""
        if isinstance(delta, dict):
            return str(delta.get("content") or "")
        return str(getattr(delta, "content", None) or "")
    except Exception:
        return ""


def _chunk_model_id(chunk: Any, fallback: str) -> str:
    mid = getattr(chunk, "model", None)
    if isinstance(mid, str) and mid.strip():
        return mid.strip()
    return fallback


def _log_advisor_usage(*, model: str, usage: dict[str, Any] | None, streaming: bool) -> None:
    logger.info(
        "logis_advisor_llm usage=%s model=%s stream=%s",
        json.dumps(usage, ensure_ascii=False, default=str) if usage is not None else "null",
        model,
        streaming,
    )


async def _verifactu_snapshot(*, db: SupabaseAsync, empresa_id: str) -> dict[str, Any]:
    eid = str(empresa_id).strip()
    try:
        q = filter_not_deleted(
            db.table("facturas")
            .select(
                "id,numero_factura,num_factura,fecha_emision,nif_emisor,total_factura,"
                "fingerprint_hash,previous_fingerprint"
            )
            .eq("empresa_id", eid)
            .order("fecha_emision", desc=False)
            .order("numero_secuencial", desc=False)
            .order("id", desc=False)
        )
        res: Any = await db.execute(q)
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    except Exception as exc:
        logger.info("advisor verifactu snapshot: %s", exc)
        return {"error": str(exc), "facturas_considered": 0}

    report = verify_invoice_chain(list(rows))
    return {
        "verifactu_chain_audit": report,
        "facturas_in_chain": len(rows),
    }


async def _flota_normativa_snapshot(*, db: SupabaseAsync, empresa_id: str) -> dict[str, Any]:
    eid = str(empresa_id).strip()
    out: dict[str, int] = {}
    euro_iii: list[dict[str, str]] = []
    try:
        res: Any = await db.execute(
            filter_not_deleted(db.table("flota").select("id,matricula,normativa_euro").eq("empresa_id", eid))
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    except Exception as exc:
        return {"error": str(exc), "counts_by_normativa": {}, "euro_iii_vehicles_sample": []}

    for r in rows:
        n = str(r.get("normativa_euro") or "").strip() or "Euro VI"
        out[n] = out.get(n, 0) + 1
        nu = n.upper()
        if "III" in nu or "EURO 3" in nu or "EURO III" in nu:
            euro_iii.append(
                {
                    "id": str(r.get("id") or ""),
                    "matricula": str(r.get("matricula") or "")[:32],
                    "normativa_euro": n[:64],
                }
            )
    return {
        "counts_by_normativa": out,
        "euro_iii_vehicles_sample": euro_iii[:12],
        "euro_iii_total": len(euro_iii),
    }


async def _build_cip_matrix_snapshot(
    *,
    db: SupabaseAsync,
    empresa_id: str,
    portes: PortesService,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Replica la lógica de ``GET /api/v1/finance/analytics/cip-matrix`` (mismos buckets).
    Devuelve (puntos_cip, vampiros_heuristicos).
    """
    from app.api.v1.finance_dashboard import (
        _fetch_portes_para_cip_matrix,
        _km_aplicable_porte,
        _ruta_display,
        _ruta_normalizada_key,
        _to_float,
    )

    eid = str(empresa_id).strip()
    coste_km = await portes.operational_cost_per_km_eur(empresa_id=eid, default=1.10)
    rows = await _fetch_portes_para_cip_matrix(db=db, empresa_id=eid)
    rows = [r for r in rows if str(r.get("estado") or "").strip().lower() != "cancelado"]

    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _ruta_normalizada_key(row)
        if not key:
            continue
        ingreso = max(0.0, _to_float(row.get("precio_pactado")))
        km = _km_aplicable_porte(row)
        coste = km * coste_km
        raw = row.get("co2_kg")
        if raw is None:
            raw = row.get("co2_emitido")
        if raw is None:
            emisiones = km * 0.62
        else:
            emisiones = max(0.0, _to_float(raw))
        if key not in buckets:
            buckets[key] = {
                "display": _ruta_display(row),
                "n": 0,
                "ingresos": 0.0,
                "costes": 0.0,
                "emisiones": 0.0,
            }
        b = buckets[key]
        b["n"] += 1
        b["ingresos"] += ingreso
        b["costes"] += coste
        b["emisiones"] += emisiones

    points: list[dict[str, Any]] = []
    for _k, b in buckets.items():
        n = int(b["n"])
        if n < 2:
            continue
        ing = float(b["ingresos"])
        cst = float(b["costes"])
        margen = round(ing - cst, 2)
        emi = round(float(b["emisiones"]), 6)
        points.append(
            {
                "ruta": str(b["display"]),
                "margen_neto": margen,
                "emisiones_co2_kg": emi,
                "total_portes": n,
            }
        )
    points.sort(key=lambda r: r["margen_neto"], reverse=True)

    vampiros: list[dict[str, Any]] = []
    for p in points:
        if p["margen_neto"] < 0 and p["emisiones_co2_kg"] > 0:
            vampiros.append(
                {
                    **p,
                    "interpretacion": (
                        "Vampiro CIP potencial: margen neto negativo con emisiones significativas; "
                        "revisar asignación de vehículo y renovación (Euro VI / ESG)."
                    ),
                }
            )
    return points, vampiros


async def gather_advisor_context(
    *,
    db: SupabaseAsync,
    empresa_id: str | UUID,
    finance: FinanceService,
    portes: PortesService,
    audit_logs: AuditLogsService,
) -> dict[str, Any]:
    """
    Agrega snapshots JSON para el prompt: EBITDA/métricas, CIP, cashflow, cumplimiento.
    """
    eid = str(empresa_id).strip()

    summary = await finance.financial_summary(empresa_id=eid)
    dash = await finance.financial_dashboard(empresa_id=eid)
    adv = await finance.advanced_metrics_last_six_months(empresa_id=eid)

    cip_points, cip_vampiros = await _build_cip_matrix_snapshot(db=db, empresa_id=eid, portes=portes)
    vf = await _verifactu_snapshot(db=db, empresa_id=eid)
    flota = await _flota_normativa_snapshot(db=db, empresa_id=eid)

    logs = await audit_logs.list_for_empresa(empresa_id=eid, limit=15)
    audit_compact = [
        {
            "table": x.table_name,
            "action": x.action,
            "record_id": str(x.record_id)[:64],
            "created_at": x.created_at.isoformat() if x.created_at else None,
        }
        for x in logs
    ]

    return {
        "ebitda_snapshot": {
            "ingresos_netos_sin_iva_eur": round(float(summary.ingresos), 2),
            "gastos_netos_sin_iva_eur": round(float(summary.gastos), 2),
            "ebitda_aprox_sin_iva_eur": round(float(summary.ebitda), 2),
        },
        "cashflow_tesoreria": {
            "tesoreria_mensual": [x.model_dump() for x in (dash.tesoreria_mensual or [])][-8:],
            "ingresos_vs_gastos_mensual": [x.model_dump() for x in (dash.ingresos_vs_gastos_mensual or [])][-8:],
            "margen_km_eur": dash.margen_km_eur,
            "km_facturados_mes_actual": dash.km_facturados_mes_actual,
        },
        "advanced_metrics_6m": {
            "meses": [m.model_dump() for m in (adv.meses or [])],
            "nota_metodologia": adv.nota_metodologia,
        },
        "cip_matrix": cip_points[:40],
        "cip_vampiros": cip_vampiros[:15],
        "flota_normativa": flota,
        "compliance": {
            "verifactu": vf,
            "audit_logs_recientes": audit_compact,
        },
    }


async def get_advisor_response(
    query: str,
    empresa_id: UUID | str,
    *,
    context: dict[str, Any],
) -> tuple[str, str]:
    """Respuesta completa (no streaming). Devuelve (texto, model_id efectivo)."""
    if not advisor_llm_configured():
        raise RuntimeError("Credenciales LLM no configuradas (p. ej. OPENAI_API_KEY / ANTHROPIC_API_KEY)")

    ctx = json.dumps(context, ensure_ascii=False, default=str)
    messages = [
        {"role": "system", "content": LOGIS_ADVISOR_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"Contexto JSON del tenant (empresa_id interno {str(empresa_id)[:8]}…):\n```json\n{ctx}\n```",
        },
        {"role": "user", "content": query.strip()},
    ]

    last_exc: Exception | None = None
    for model in _model_chain():
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=0.25,
            )
            text = _completion_text(response)
            resolved = _response_model_id(response, model)
            usage = _usage_to_dict(getattr(response, "usage", None))
            _log_advisor_usage(model=resolved, usage=usage, streaming=False)
            return _redact_leaks(text.strip()), resolved
        except Exception as exc:
            last_exc = exc
            logger.warning("advisor get_advisor_response falló model=%s: %s", model, exc, exc_info=False)

    raise RuntimeError("No se pudo completar la respuesta con ningún modelo configurado") from last_exc


async def stream_advisor_response(
    query: str,
    empresa_id: UUID | str,
    *,
    context: dict[str, Any],
) -> AsyncIterator[tuple[str, str | None]]:
    """Emite (fragmento, None) y al final ("", model_id efectivo). Chunks estilo OpenAI."""
    if not advisor_llm_configured():
        raise RuntimeError("Credenciales LLM no configuradas (p. ej. OPENAI_API_KEY / ANTHROPIC_API_KEY)")

    ctx = json.dumps(context, ensure_ascii=False, default=str)
    messages = [
        {"role": "system", "content": LOGIS_ADVISOR_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"Contexto JSON del tenant (empresa_id interno {str(empresa_id)[:8]}…):\n```json\n{ctx}\n```",
        },
        {"role": "user", "content": query.strip()},
    ]

    last_exc: Exception | None = None
    for model in _model_chain():
        usage_accum: dict[str, Any] | None = None
        try:
            stream_kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": True,
                "temperature": 0.25,
            }
            # OpenAI admite usage en el último chunk; otros proveedores ignoran vía ``drop_params``.
            ml = model.lower()
            if ml.startswith("openai/") or ml.startswith("azure") or ml.startswith("azure/"):
                stream_kwargs["stream_options"] = {"include_usage": True}
            stream = await litellm.acompletion(**stream_kwargs)
            resolved = model
            async for chunk in stream:
                resolved = _chunk_model_id(chunk, resolved)
                delta = _delta_from_chunk(chunk)
                if delta:
                    yield _redact_leaks(delta), None
                u = getattr(chunk, "usage", None)
                if u is not None:
                    usage_accum = _usage_to_dict(u)

            _log_advisor_usage(model=resolved, usage=usage_accum, streaming=True)
            yield "", resolved
            return
        except Exception as exc:
            last_exc = exc
            logger.warning("advisor stream_advisor_response falló model=%s: %s", model, exc, exc_info=False)

    raise RuntimeError("No se pudo completar el streaming con ningún modelo configurado") from last_exc
