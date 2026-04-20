"""
LogisAdvisor: contexto agregado (finanzas, CIP, tesorería, cumplimiento) + LLM.

Usa **LiteLLM** (`litellm.acompletion`) para varios proveedores; las claves se resuelven vía ``get_secret_manager()``.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import math
import os
import re
from collections.abc import AsyncIterator
from datetime import date
from typing import Any, Optional
from uuid import UUID

import litellm

from app.core.verifactu import verify_invoice_chain
from app.services.verifactu_fingerprint_audit import (
    load_cliente_nif_map_for_facturas,
    materialize_factura_rows_for_fingerprint_verify,
)
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.porte import PorteOut
from app.services.audit_logs_service import AuditLogsService
from app.services.bi_service import BiService
from app.services.finance_service import FinanceService
from app.services.maps_service import MapsService
from app.services.matching_service import MatchingService
from app.services.portes_service import PortesService
from app.services.secret_manager_service import get_secret_manager

litellm.drop_params = True

logger = logging.getLogger(__name__)

LOGIS_ADVISOR_GEO_APPEND = """
**CAPACIDADES GEOGRÁFICAS:**
Tienes acceso a las coordenadas (lat, lng) de los portes activos.
Tu objetivo es minimizar el "Kilometraje en Vacío" (Deadhead miles) y maximizar el EBITDA por ruta.

**REGLAS TÁCTICAS Y ZBE:**
- **Alerta ZBE**: Si un vehículo 'Vampiro' (Euro III o sin etiqueta) se dirige a una Zona de Bajas Emisiones (ej. Madrid 360, ZBE Barcelona), debes sugerir un trasbordo o cambio de ruta inmediatamente.
- **Optimización de Retorno**: Identifica si un vehículo termina un porte cerca de otro origen pendiente (<50km) y recomienda la asignación para optimizar el flujo.
- **Riesgo de Margen**: Si la ruta detectada tiene una desviación de rentabilidad basada en el coste real de 0.62€/km, avisa al usuario.

**Índice de Desviación Rentable (I_dr):**
Cada porte en `geo_intel.fleet_geo_rows` incluye `indice_desviacion_rentable` (campos `i_dr`, `sugerir_proactivo`, etc.).
Definición operativa: I_dr = Δ Margen de contribución estimado / (coste de desvío km + penalización ESG).
Si I_dr > 1 en una fila, debes proponer de forma proactiva la optimización (reordenación de portes, cambio de tractora o evitar ZBE con Euro III).
"""


LOGIS_ADVISOR_BI_APPEND = """
**Inteligencia BI (bloque ``bi_intelligence`` del JSON):**
- **``dashboard_summary``**: DSO real (días entre emisión y cobro bancario en facturas conciliadas), eficiencia media (ratio precio / (km×0,62)), CO₂ ahorrado agregado y tamaños de muestra.
- **Prioridad 1 — Avisos de liquidez (DSO):** Si ``dso_days`` es elevado o la muestra ``dso_sample_size`` es significativa, explica el **riesgo de caja** (capital circulante, tensiones de tesorería). Cruza con **``clientes_presion_cobro``** (cartera pendiente por cliente).
- **Prioridad 2 — Fugas de rentabilidad (eficiencia η):** En **``routes_efficiency_below_1``**, cada fila incluye **``efficiency_eta``** = precio / (km × coste/km). η < 1 indica trayecto por debajo del umbral de referencia operativa: prioriza rutas, cliente y acciones (precio, km, carga, asignación de vehículo).
- Preguntas tipo *«¿qué clientes pagan peor?»* o *«impacto en caja»*: usa **solo** **``clientes_presion_cobro``** (orden descendente de severidad) y **``dashboard_summary``**; no inventes clientes ni importes.
- Si ``bi_intelligence`` falta o trae ``error``, no asumas cifras BI.
"""


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
    "**Conciliación bancaria (motor de emparejamiento):**\n"
    "- El JSON puede incluir ``bank_reconciliation_hints`` con ``high_confidence_matches`` (sugerencias calculadas, **no** aplicadas en ERP).\n"
    "- Si hay emparejamientos de alta confianza (p. ej. ``score`` ≥ 0,85), **infórmalo** de forma concreta (qué movimiento encaja con qué factura según el contexto) y **pide confirmación explícita** al usuario antes de dar por hecho que el cobro/pago quedó conciliado.\n"
    "- No afirmes que la conciliación está cerrada en contabilidad hasta que el usuario confirme o ejecute la acción de conciliar en la aplicación.\n\n"
    "**Formato**: Markdown breve; no inventes cifras fuera del contexto. No expongas datos bancarios ni credenciales."
    + "\n\n"
    + LOGIS_ADVISOR_BI_APPEND.strip()
    + "\n\n"
    + LOGIS_ADVISOR_GEO_APPEND.strip()
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
    mgr = get_secret_manager()
    return bool(
        mgr.get_openai_api_key()
        or mgr.get_anthropic_api_key()
        or mgr.get_azure_openai_api_key()
        or mgr.get_google_gemini_api_key()
    )


def _litellm_api_key_for_model(model: str) -> Optional[str]:
    """Resuelve la clave adecuada para ``litellm.acompletion`` según el prefijo del modelo."""
    ml = model.strip().lower()
    mgr = get_secret_manager()
    if ml.startswith("openai/") or ml.startswith("gpt-"):
        return mgr.get_openai_api_key()
    if ml.startswith("anthropic/"):
        return mgr.get_anthropic_api_key()
    if ml.startswith("azure") or ml.startswith("azure/"):
        return mgr.get_azure_openai_api_key()
    if "gemini" in ml:
        return mgr.get_google_gemini_api_key()
    return mgr.get_openai_api_key()


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
                "id,cliente,numero_factura,num_factura,fecha_emision,nif_emisor,total_factura,"
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

    nif_map = await load_cliente_nif_map_for_facturas(db, empresa_id=eid, rows=rows)
    rows_m = materialize_factura_rows_for_fingerprint_verify(rows, cliente_nif_map=nif_map)
    report = verify_invoice_chain(list(rows_m))
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


# Coste operativo €/km (alineado con front Fleet map / reglas tácticas).
COSTE_OPERATIVO_EUR_KM: float = 0.62
GEO_PORTE_LIMIT: int = 25


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distancia en km entre (lat,lng) y (lat,lng)."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(h)))


def _normativa_euro_str(row: dict[str, Any] | None) -> str:
    if not row:
        return "desconocido"
    return str(row.get("normativa_euro") or row.get("engine_class") or "desconocido")[:64]


def _is_euro_iii_row(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    ne = str(row.get("normativa_euro") or "").upper()
    ec = str(row.get("engine_class") or "").upper()
    cert = str(row.get("certificacion_emisiones") or "")
    blob = f"{ne} {ec} {cert}".upper()
    return "III" in blob or "EURO 3" in blob or "EURO_III" in ec


def _zbe_spain_hint(
    *,
    dest_lat: float | None,
    dest_lng: float | None,
    dest_address: str,
) -> dict[str, Any]:
    """Heurística española: núcleos con ZBE / Madrid 360 / Rondas."""
    addr = (dest_address or "").lower()
    keywords = (
        "zbe",
        "madrid 360",
        "barcelona",
        "rondas",
        "madrid centro",
        "gran vía",
        "eixample",
        "rondes",
    )
    if any(k in addr for k in keywords):
        return {"zbe_probable": True, "zona_guess": "Por texto de destino (ZBE probable)"}
    if dest_lat is not None and dest_lng is not None:
        if 40.25 <= dest_lat <= 40.52 and -3.95 <= dest_lng <= -3.55:
            return {"zbe_probable": True, "zona_guess": "Madrid capital / Madrid 360 (coord.)"}
        if 41.30 <= dest_lat <= 41.48 and 2.05 <= dest_lng <= 2.25:
            return {"zbe_probable": True, "zona_guess": "AMB Barcelona / ZBE (coord.)"}
        if 39.40 <= dest_lat <= 39.50 and -0.40 <= dest_lng <= -0.30:
            return {"zbe_probable": True, "zona_guess": "València / área restricciones (coord.)"}
    return {"zbe_probable": False, "zona_guess": None}


def _fleet_status_label(
    *,
    euro_iii: bool,
    low_margin: bool,
    high_margin_low_co2: bool,
) -> str:
    if euro_iii or low_margin:
        return "Vampiro"
    if high_margin_low_co2:
        return "Estrella"
    return "Operativo"


def _compute_idr(
    *,
    precio: float,
    km_maps: float,
    km_declarados: float,
    vampire: bool,
    zbe: bool,
) -> dict[str, Any]:
    """
    I_dr = Δ MC / (coste desvío + penalización ESG).
    Δ MC ~ margen de contribución estimado (precio - coste operativo por km real).
    """
    km_m = max(km_maps, 1e-6)
    delta_mc = precio - km_m * COSTE_OPERATIVO_EUR_KM
    coste_desvio = abs(km_maps - km_declarados) * COSTE_OPERATIVO_EUR_KM
    pen_esg = (km_m * 0.12) if (vampire and zbe) else 0.0
    denom = coste_desvio + pen_esg + 1e-9
    i_dr = float(delta_mc / denom) if denom > 0 else 0.0
    return {
        "i_dr": round(i_dr, 4),
        "delta_margen_contribucion_eur": round(delta_mc, 2),
        "coste_desvio_eur": round(coste_desvio, 2),
        "penalizacion_esg_eur": round(pen_esg, 2),
        "sugerir_proactivo": bool(i_dr > 1.0),
    }


async def _geo_aware_fleet_context(
    *,
    db: SupabaseAsync,
    empresa_id: str,
    portes_svc: PortesService,
    maps: MapsService,
) -> dict[str, Any]:
    """
    Portes pendientes + distancia Google (caché MapsService) + geocodificación + heurísticas tácticas.
    """
    eid = str(empresa_id).strip()
    try:
        pendientes: list[PorteOut] = await portes_svc.list_portes_pendientes(empresa_id=eid)
    except Exception as exc:
        return {"error": str(exc), "fleet_rows": [], "fleet_data_llm_lines": []}

    pendientes = pendientes[:GEO_PORTE_LIMIT]

    flota_by_id: dict[str, dict[str, Any]] = {}
    try:
        res_fl: Any = await db.execute(
            filter_not_deleted(
                db.table("flota")
                .select("id,matricula,normativa_euro,engine_class,certificacion_emisiones")
                .eq("empresa_id", eid)
            )
        )
        for r in (res_fl.data or []) if hasattr(res_fl, "data") else []:
            if r.get("id") is not None:
                flota_by_id[str(r["id"])] = dict(r)
    except Exception:
        pass

    sem = asyncio.Semaphore(4)

    async def enrich_one(p: PorteOut) -> dict[str, Any]:
        async with sem:
            vid = str(p.vehiculo_id).strip() if p.vehiculo_id else ""
            vrow = flota_by_id.get(vid) if vid else None
            euro_iii = _is_euro_iii_row(vrow)
            precio = float(p.precio_pactado or 0)
            km_decl = max(float(p.km_estimados or 0), 0.0)

            try:
                km_maps = await maps.get_distance_km(
                    p.origen,
                    p.destino,
                    tenant_empresa_id=eid,
                )
            except Exception:
                km_maps = max(km_decl, 0.01) if km_decl > 0 else 1.0

            o_geo = await maps.geocode_lat_lng(p.origen)
            d_geo = await maps.geocode_lat_lng(p.destino)

            co2 = float(p.co2_emitido) if p.co2_emitido is not None else None
            co2_pk = (co2 / km_maps) if (co2 is not None and km_maps > 0) else None
            eur_km = precio / km_maps if km_maps > 0 else 0.0
            margen_km = eur_km - COSTE_OPERATIVO_EUR_KM
            low_margin = margen_km < 0.28
            high_margin_low_co2 = (
                margen_km >= 0.55
                and co2_pk is not None
                and co2_pk <= 2.1
                and not euro_iii
            )
            status = _fleet_status_label(
                euro_iii=euro_iii,
                low_margin=low_margin,
                high_margin_low_co2=high_margin_low_co2,
            )

            zbe = _zbe_spain_hint(
                dest_lat=d_geo[0] if d_geo else None,
                dest_lng=d_geo[1] if d_geo else None,
                dest_address=p.destino,
            )
            zbe_flag = bool(zbe.get("zbe_probable"))

            idr = _compute_idr(
                precio=precio,
                km_maps=km_maps,
                km_declarados=km_decl,
                vampire=(status == "Vampiro"),
                zbe=zbe_flag,
            )

            orig_ll = {"lat": o_geo[0], "lng": o_geo[1]} if o_geo else None
            dest_ll = {"lat": d_geo[0], "lng": d_geo[1]} if d_geo else None

            return {
                "porte_id": str(p.id),
                "vehiculo_id": vid or None,
                "matricula": (vrow or {}).get("matricula"),
                "normativa_euro": _normativa_euro_str(vrow),
                "status_intel": status,
                "origin_address": p.origen,
                "dest_address": p.destino,
                "origin_lat_lng": orig_ll,
                "dest_lat_lng": dest_ll,
                "distancia_km_maps": round(km_maps, 4),
                "km_estimados_declarados": round(km_decl, 4),
                "est_margen_eur_km": round(margen_km, 4),
                "zbe": zbe,
                "indice_desviacion_rentable": idr,
                "euro_iii": euro_iii,
            }

    async def safe_enrich(p: PorteOut) -> dict[str, Any]:
        try:
            return await enrich_one(p)
        except Exception as exc:
            return {"porte_id": str(p.id), "error": str(exc)[:200]}

    enriched: list[dict[str, Any]] = list(await asyncio.gather(*[safe_enrich(p) for p in pendientes]))

    lines: list[str] = []
    for row in enriched:
        if row.get("error"):
            continue
        vid = row.get("vehiculo_id") or "sin_asignar"
        st = row.get("status_intel") or "?"
        oll = row.get("origin_lat_lng")
        cur = f"{oll['lat']:.4f},{oll['lng']:.4f}" if isinstance(oll, dict) else "sin_coord"
        dest = str(row.get("dest_address") or "")[:120]
        em = row.get("est_margen_eur_km")
        eu = row.get("normativa_euro") or "?"
        lines.append(
            f"[{vid} | {st} | {cur} | {dest} | {em} | {eu}]",
        )

    pairing: list[dict[str, Any]] = []
    ok_rows = [r for r in enriched if not r.get("error") and r.get("dest_lat_lng") and r.get("origin_lat_lng")]
    for i, a in enumerate(ok_rows):
        da = a.get("dest_lat_lng") or {}
        ta = (float(da["lat"]), float(da["lng"]))
        for j, b in enumerate(ok_rows):
            if i >= j:
                continue
            ob = b.get("origin_lat_lng") or {}
            tb = (float(ob["lat"]), float(ob["lng"]))
            dkm = _haversine_km(ta, tb)
            if dkm < 50.0:
                pairing.append(
                    {
                        "fin_porte_id": a.get("porte_id"),
                        "cerca_origen_porte_id": b.get("porte_id"),
                        "km_entre_descarga_y_siguiente_carga": round(dkm, 2),
                        "nota": "Posible optimización de retorno / menos vacío",
                    }
                )

    alertas: list[dict[str, Any]] = []
    for row in ok_rows:
        pid = row.get("porte_id")
        idr = row.get("indice_desviacion_rentable") or {}
        if isinstance(idr, dict) and idr.get("sugerir_proactivo"):
            alertas.append(
                {
                    "tipo": "I_dr>1",
                    "porte_id": pid,
                    "detalle": "Índice de desviación rentable favorable a actuar (ver fórmula en contexto).",
                }
            )
        zbe = row.get("zbe") or {}
        if row.get("status_intel") == "Vampiro" and zbe.get("zbe_probable"):
            alertas.append(
                {
                    "tipo": "ZBE+Vampiro",
                    "porte_id": pid,
                    "detalle": "Riesgo ZBE con tractora Euro III o margen crítico; valorar trasbordo o cambio de ruta.",
                }
            )
        km_d = float(row.get("km_estimados_declarados") or 0)
        km_m = float(row.get("distancia_km_maps") or 0)
        if km_d > 0 and abs(km_m - km_d) * COSTE_OPERATIVO_EUR_KM > 80:
            alertas.append(
                {
                    "tipo": "desviacion_km",
                    "porte_id": pid,
                    "detalle": "Gran desviación entre km declarados y km ruta Google; revisar coste a 0.62€/km.",
                }
            )

    return {
        "fleet_geo_rows": enriched[:GEO_PORTE_LIMIT],
        "fleet_data_llm_lines": lines,
        "optimizacion_retorno_km50": pairing[:12],
        "alertas_tacticas": alertas[:20],
        "nota_formato_llm": (
            "Cada línea en fleet_data_llm_lines sigue: "
            "[Vehicle_ID | Status | Current_Location(lat,lng) | Destination | Est_Margin_EUR_KM | Euro_Norm]"
        ),
    }


def mask_advisor_context_for_rbac(ctx: dict[str, Any], *, rbac_role: str) -> dict[str, Any]:
    """
    Oculta EBITDA y márgenes netos al rol ``traffic_manager`` (contexto JSON hacia el LLM / trazas).
    """
    r = (rbac_role or "").strip().lower()
    if r != "traffic_manager":
        return ctx
    out = copy.deepcopy(ctx)

    br = out.get("bank_reconciliation_hints")
    if br is not None:
        out["bank_reconciliation_hints"] = {
            "masked_for_role": True,
            "note": "Sugerencias de conciliación bancaria no expuestas a este rol.",
        }

    snap = out.get("ebitda_snapshot")
    if isinstance(snap, dict):
        for k in ("ingresos_netos_sin_iva_eur", "gastos_netos_sin_iva_eur", "ebitda_aprox_sin_iva_eur"):
            if k in snap:
                snap[k] = None

    cf = out.get("cashflow_tesoreria")
    if isinstance(cf, dict):
        for k in (
            "margen_km_eur",
            "margen_neto_km_mes_actual",
            "margen_neto_km_mes_anterior",
            "variacion_margen_km_pct",
        ):
            if k in cf:
                cf[k] = None
        bars = cf.get("ingresos_vs_gastos_mensual")
        if isinstance(bars, list):
            for row in bars:
                if isinstance(row, dict):
                    row["ingresos"] = None
                    row["gastos"] = None

    adv = out.get("advanced_metrics_6m")
    if isinstance(adv, dict):
        meses = adv.get("meses")
        if isinstance(meses, list):
            for m in meses:
                if isinstance(m, dict):
                    m["margen_contribucion_eur"] = None
                    m["ebitda_verde_eur_por_kg_co2"] = None

    for key in ("cip_matrix", "cip_vampiros"):
        pts = out.get(key)
        if isinstance(pts, list):
            for p in pts:
                if isinstance(p, dict) and "margen_neto" in p:
                    p["margen_neto"] = None

    geo = out.get("geo_intel")
    if isinstance(geo, dict):
        rows = geo.get("fleet_geo_rows")
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                row["est_margen_eur_km"] = None
                idr = row.get("indice_desviacion_rentable")
                if isinstance(idr, dict):
                    idr["delta_margen_contribucion_eur"] = None
                    idr["i_dr"] = None
        geo["fleet_data_llm_lines"] = []

    bi = out.get("bi_intelligence")
    if isinstance(bi, dict):
        out["bi_intelligence"] = {
            "masked_for_role": True,
            "nota": "Métricas BI (liquidez, η por trayecto y cartera por cliente) no expuestas a este rol.",
        }

    return out


def _factura_cliente_uuid(row: dict[str, Any]) -> str:
    v = row.get("cliente_id")
    if v is None:
        v = row.get("cliente")
    return str(v or "").strip()


def _nested_cliente_nombre(row: dict[str, Any]) -> str | None:
    c = row.get("clientes")
    if isinstance(c, dict):
        n = str(c.get("nombre") or "").strip()
        return n or None
    if isinstance(c, list) and c and isinstance(c[0], dict):
        n = str(c[0].get("nombre") or "").strip()
        return n or None
    return None


def _parse_fecha_emision_factura(raw: Any) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw
    if hasattr(raw, "date"):
        try:
            return raw.date()  # type: ignore[no-any-return, union-attr]
        except Exception:
            return None
    s = str(raw).strip()[:10]
    if len(s) < 10:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


async def _client_payment_pressure_ranking(*, db: SupabaseAsync, empresa_id: str) -> list[dict[str, Any]]:
    """
    Clientes con mayor presión de cobro: facturas no cobradas agregadas por cliente,
    importe pendiente y antigüedad máxima (días desde emisión).
    """
    eid = str(empresa_id).strip()
    rows: list[dict[str, Any]] = []
    try:
        res: Any = await db.execute(
            db.table("facturas")
            .select("id, cliente_id, cliente, total_factura, fecha_emision, estado_cobro, clientes(nombre)")
            .eq("empresa_id", eid)
            .order("fecha_emision", desc=True)
            .limit(500)
        )
        rows = (res.data or []) if hasattr(res, "data") else []
    except Exception:
        try:
            res2: Any = await db.execute(
                db.table("facturas")
                .select("id, cliente_id, cliente, total_factura, fecha_emision, estado_cobro")
                .eq("empresa_id", eid)
                .order("fecha_emision", desc=True)
                .limit(500)
            )
            rows = (res2.data or []) if hasattr(res2, "data") else []
        except Exception:
            logger.exception("client_payment_pressure: fetch facturas")
            return []

    today = date.today()
    agg: dict[str, dict[str, Any]] = {}

    for r in rows:
        st = str(r.get("estado_cobro") or "").strip().lower()
        if st == "cobrada":
            continue
        cid = _factura_cliente_uuid(r)
        if not cid:
            continue
        try:
            tf = float(r.get("total_factura") or 0)
        except (TypeError, ValueError):
            tf = 0.0
        fe = _parse_fecha_emision_factura(r.get("fecha_emision"))
        days_open = max(0, (today - fe).days) if fe else 0

        if cid not in agg:
            agg[cid] = {
                "cliente_id": cid,
                "cliente_nombre": _nested_cliente_nombre(r),
                "facturas_pendientes": 0,
                "importe_pendiente_eur": 0.0,
                "dias_antiguedad_max": 0,
            }
        a = agg[cid]
        a["facturas_pendientes"] = int(a["facturas_pendientes"]) + 1
        a["importe_pendiente_eur"] = float(a["importe_pendiente_eur"]) + tf
        nm = _nested_cliente_nombre(r)
        if nm:
            a["cliente_nombre"] = nm
        if days_open > int(a["dias_antiguedad_max"]):
            a["dias_antiguedad_max"] = days_open

    missing = [k for k, v in agg.items() if not str(v.get("cliente_nombre") or "").strip()]
    if missing:
        for i in range(0, len(missing), 80):
            chunk = missing[i : i + 80]
            try:
                res3: Any = await db.execute(
                    db.table("clientes").select("id, nombre").eq("empresa_id", eid).in_("id", chunk)
                )
                for row in (res3.data or []) if hasattr(res3, "data") else []:
                    cid = str(row.get("id") or "").strip()
                    nm = str(row.get("nombre") or "").strip()
                    if cid in agg and nm:
                        agg[cid]["cliente_nombre"] = nm
            except Exception:
                logger.exception("client_payment_pressure: fetch nombres")

    def severity(v: dict[str, Any]) -> float:
        imp = float(v.get("importe_pendiente_eur") or 0)
        days = float(v.get("dias_antiguedad_max") or 0)
        return imp * (1.0 + min(days, 540) / 30.0)

    out_list = sorted(agg.values(), key=severity, reverse=True)
    for item in out_list:
        item["score_presion_cobro"] = round(severity(item), 2)
        item["importe_pendiente_eur"] = round(float(item["importe_pendiente_eur"]), 2)
    return out_list


async def _build_bi_intelligence(*, db: SupabaseAsync, empresa_id: str, bi: BiService) -> dict[str, Any]:
    """Resumen BI + rutas con η<1 + ranking de presión de cobro por cliente."""
    eid = str(empresa_id).strip()
    try:
        summary = await bi.dashboard_summary(empresa_id=eid)
        prof = await bi.profitability_scatter(empresa_id=eid)
        coste = float(prof.coste_operativo_eur_km or 0.62)
        routes: list[dict[str, Any]] = []
        for pt in prof.points:
            precio = float(pt.precio_pactado or 0)
            denom = float(pt.km) * coste
            eta = precio / denom if denom > 1e-9 else 0.0
            if eta < 1.0:
                routes.append(
                    {
                        "route_label": (pt.route_label or "").strip() or None,
                        "porte_id": str(pt.porte_id),
                        "efficiency_eta": round(eta, 4),
                        "km": pt.km,
                        "margin_eur": pt.margin_eur,
                        "cliente": pt.cliente,
                        "vehiculo": pt.vehiculo,
                    }
                )
        routes.sort(key=lambda x: float(x.get("efficiency_eta") or 0))
        clientes = await _client_payment_pressure_ranking(db=db, empresa_id=eid)
        return {
            "dashboard_summary": summary.model_dump(),
            "coste_operativo_eur_km_used": round(coste, 4),
            "routes_efficiency_below_1": routes[:50],
            "routes_efficiency_below_1_total": len(routes),
            "clientes_presion_cobro": clientes[:15],
            "nota_metodologia": (
                "η = precio_pactado / (km × coste/km). clientes_presion_cobro ordenado por score_presion_cobro "
                "(importe pendiente ponderado por antigüedad máxima en días)."
            ),
        }
    except Exception:
        logger.exception("_build_bi_intelligence")
        return {"error": "bi_context_unavailable"}


async def gather_advisor_context(
    *,
    db: SupabaseAsync,
    empresa_id: str | UUID,
    finance: FinanceService,
    portes: PortesService,
    audit_logs: AuditLogsService,
    maps: MapsService,
    bi: BiService | None = None,
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
    geo_intel = await _geo_aware_fleet_context(db=db, empresa_id=eid, portes_svc=portes, maps=maps)

    bank_reconciliation_hints: dict[str, Any] = {"error": "matching_unavailable"}
    try:
        match_svc = MatchingService(db=db)
        bank_reconciliation_hints = await match_svc.find_matches(empresa_id=eid, threshold=0.85)
    except Exception:
        logger.exception("gather_advisor_context: find_matches")

    try:
        logs = await audit_logs.list_for_empresa(empresa_id=eid, limit=15)
    except Exception:
        logger.exception("gather_advisor_context: audit_logs")
        logs = []
    audit_compact = [
        {
            "table": x.table_name,
            "action": x.action,
            "record_id": str(x.record_id)[:64],
            "created_at": x.created_at.isoformat() if x.created_at else None,
        }
        for x in logs
    ]

    bi_svc = bi or BiService(db)
    bi_intel = await _build_bi_intelligence(db=db, empresa_id=eid, bi=bi_svc)

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
        "geo_intel": geo_intel,
        "bank_reconciliation_hints": bank_reconciliation_hints,
        "bi_intelligence": bi_intel,
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
        api_key = _litellm_api_key_for_model(model)
        if not api_key:
            logger.warning("advisor: sin api_key para model=%s; se prueba el siguiente", model)
            last_exc = RuntimeError(f"Sin credenciales LLM para model={model!r}")
            continue
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=0.25,
                api_key=api_key,
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
        api_key = _litellm_api_key_for_model(model)
        if not api_key:
            logger.warning("advisor stream: sin api_key para model=%s; se prueba el siguiente", model)
            last_exc = RuntimeError(f"Sin credenciales LLM para model={model!r}")
            continue
        usage_accum: dict[str, Any] | None = None
        try:
            stream_kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": True,
                "temperature": 0.25,
                "api_key": api_key,
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
