from __future__ import annotations

import json
import logging
import os
import re
from datetime import date
from collections.abc import AsyncIterator
from typing import Any
import litellm

from app.core.constants import COSTE_OPERATIVO_EUR_KM
from app.core.math_engine import quantize_currency, to_decimal
from app.core.verifactu import verify_invoice_chain
from app.services.verifactu_fingerprint_audit import (
    load_cliente_nif_map_for_facturas,
    materialize_factura_rows_for_fingerprint_verify,
)
from app.services.esg_service import EsgService
from app.services.facturas_service import FacturasService
from app.services.finance_service import FinanceService
from app.services.flota_service import FlotaService
from app.services.maps_service import MapsService
from app.services.secret_manager_service import get_secret_manager
from app.schemas.banking import ConciliationCandidate, Transaccion

logger = logging.getLogger(__name__)
litellm.drop_params = True

LOGISADVISOR_CONTEXT = """You are LogisAdvisor, Senior Logistics Consultant for AB Logistics OS (Spain).

Economic Rules:
- Use the tenant's configured operational CPK (EUR/km) from JSON context for cost estimation.
- Define route efficiency eta as Income / (Km * CPK).
- If eta < 1.15 classify it as a "Vampire Route".
- If DSO > 60 days classify it as a liquidity risk.

Compliance:
- You are fluent in VeriFactu obligations including XAdES-BES signatures and invoice chaining (hash/previous hash).

Response Priorities:
1) Profitability
2) Fiscal Safety
3) Liquidity

Behavior:
- Be proactive: surface hidden risks before user asks.
- Never invent numbers that are not present in the provided JSON context.
- Keep recommendations concrete and action-oriented.
"""

# ── Prompt system (economista senior + seguridad) ─────────────────────────────
LOGIS_ADVISOR_SYSTEM_PROMPT = """Eres **LogisAdvisor**, el asistente inteligente de **AB Logistics OS** para transporte y logística.

**Rol y estilo**
- Actúas como un **economista senior** y director de operaciones: riguroso, claro y orientado a decisiones.
- Prioriza **métricas operativas** (EBITDA aproximado sin IVA, margen por km, cobros, flota disponible, huella CO₂ cuando exista).
- Si faltan datos o una herramienta no devuelve información, dilo sin inventar cifras.

**Herramientas**
- Tienes funciones para leer resumen financiero, facturas pendientes de cobro y métricas de eficiencia de flota/rutas.
- Usa las herramientas cuando el usuario pregunte por números o listados; no supongas importes.

**Seguridad y privacidad (obligatorio)**
- **Nunca** reveles ni repitas: IBAN completos, números de cuenta bancaria, claves API, tokens, secretos de cifrado ni contraseñas.
- No expongas datos personales innecesarios (emails, teléfonos completos, direcciones completas de terceros).
- Los importes y estados de facturación son **información operativa del tenant**; está permitido resumirlos y compararlos.
- Si te piden datos bancarios o credenciales, recházalo y ofrece solo KPIs o estados agregados.

**Formato**
- Puedes usar **Markdown** (tablas, listas, negritas) para KPIs y comparativas.
- Sé conciso salvo que el usuario pida detalle.
"""


def _redact_leaks(text: str) -> str:
    """Capa ligera post-respuesta: patrones típicos de IBAN / claves (no sustituye el prompt)."""
    if not text:
        return text
    # IBAN ES (24 alfanuméricos tras ES)
    text = re.sub(r"\bES\d{22}\b", "[IBAN oculto]", text, flags=re.IGNORECASE)
    # API keys estilo sk-…
    text = re.sub(r"\bsk-[A-Za-z0-9]{16,}\b", "[clave oculta]", text)
    return text


def _tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_financial_summary",
                "description": (
                    "Obtiene ingresos/gastos/EBITDA sin IVA y KPIs del dashboard financiero "
                    "(margen por km, km facturados, tesorería reciente agregada)."
                ),
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_unpaid_invoices",
                "description": (
                    "Lista facturas con cobro pendiente (no cobradas): número, fecha, total, estado y nombre de cliente. "
                    "Sin datos bancarios."
                ),
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_fleet_efficiency_metrics",
                "description": (
                    "Métricas de eficiencia operativa: disponibilidad de flota, KPIs de margen/km del dashboard financiero, "
                    "indicadores de rutas (Maps) y huella CO₂ del mes anterior vía ESG cuando sea posible."
                ),
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
    ]


class LogisAdvisorService:
    """
    Orquesta LLM (OpenAI) con herramientas sobre servicios de dominio existentes.
    El ``empresa_id`` efectivo siempre lo fija el backend (JWT), no el modelo.
    """

    def __init__(
        self,
        finance: FinanceService,
        facturas: FacturasService,
        flota: FlotaService,
        maps: MapsService,
        esg: EsgService,
    ) -> None:
        self._finance = finance
        self._facturas = facturas
        self._flota = flota
        self._maps = maps
        self._esg = esg

    @staticmethod
    def openai_configured() -> bool:
        mgr = get_secret_manager()
        return bool(
            mgr.get_openai_api_key()
            or mgr.get_google_gemini_api_key()
        )

    @staticmethod
    def model_name() -> str:
        configured = (os.getenv("LOGISADVISOR_MODEL") or "").strip()
        if configured:
            return configured
        mgr = get_secret_manager()
        if mgr.get_openai_api_key():
            return "openai/gpt-4o-mini"
        if mgr.get_google_gemini_api_key():
            return "gemini/gemini-1.5-flash"
        return "openai/gpt-4o-mini"

    async def prepare_ai_context(self, *, empresa_id: str) -> str:
        """
        Build a compact AB Logistics OS snapshot for AI consumption.

        Data Dictionary blocks:
        - ``operational``:
          - ``active_routes``: sampled routes with distance/time and source (cache/google).
          - ``cpk_eur``: operational cost per km constant (EUR/km, product default).
          - ``estimated_operational_cost_eur``: route_km * cpk_eur (MathEngine quantized).
          - ``efficiency_eta``: Income / (Km * cpk_eur). If eta < 1.15 => ``vampire_route=true``.
        - ``financial``:
          - ``ingresos_netos_sin_iva_eur``, ``gastos_netos_sin_iva_eur``, ``ebitda_aprox_sin_iva_eur``.
          - ``dso_days``: average open days for unpaid invoices; ``liquidity_risk`` when > 60.
        - ``fiscal``:
          - VeriFactu chain integrity summary from ``verify_invoice_chain`` over tenant invoices.
          - Tracks XAdES-BES/signature-chain hygiene via hash continuity indicators.

        Privacy/Security:
        - Excludes client names, IBAN/account numbers, emails, and raw invoice identifiers.
        - Route labels are hashed/truncated to preserve analytical value with minimal exposure.

        Returns:
        - Minified JSON string (``separators=(',', ':')``) to reduce token usage.
        """
        eid = str(empresa_id or "").strip()
        if not eid:
            return json.dumps(
                {"operational": {}, "financial": {}, "fiscal": {}},
                ensure_ascii=False,
                separators=(",", ":"),
            )

        # PorteRepository mapping: uses existing domain data source through service DB client.
        db = self._flota._db  # type: ignore[attr-defined]
        portes_res = await db.execute(
            db.table("portes")
            .select("id,origen,destino,precio_pactado,km_estimados,estado,fecha")
            .eq("empresa_id", eid)
            .order("fecha", desc=True)
            .limit(20)
        )
        porte_rows: list[dict[str, Any]] = (portes_res.data or []) if hasattr(portes_res, "data") else []

        active_routes: list[dict[str, Any]] = []
        total_emisiones_co2_kg = 0.0
        for row in porte_rows:
            if str(row.get("estado") or "").strip().lower() == "cancelado":
                continue
            origin = str(row.get("origen") or "").strip()
            destination = str(row.get("destino") or "").strip()
            if not origin or not destination:
                continue
            income = float(row.get("precio_pactado") or 0.0)
            route_ref = f"{origin}|{destination}"
            route_key = route_ref[:48]
            try:
                metrics = await self._maps.get_route_data(
                    origin,
                    destination,
                    tenant_empresa_id=eid,
                )
                km = float(metrics.get("distance_km") or 0.0)
                op_cost = float(quantize_currency(to_decimal(km * COSTE_OPERATIVO_EUR_KM)))
                eta = round((income / op_cost), 4) if op_cost > 1e-9 else None
                emisiones_co2_kg = self._esg.calculate_route_emissions(distance_km=km)
                total_emisiones_co2_kg += emisiones_co2_kg
                active_routes.append(
                    {
                        "route_ref": route_key,
                        "distance_km": round(km, 3),
                        "duration_mins": int(metrics.get("duration_mins") or 0),
                        "income_eur": round(income, 2),
                        "estimated_operational_cost_eur": op_cost,
                        "efficiency_eta": eta,
                        "emisiones_co2_kg": emisiones_co2_kg,
                        "vampire_route": bool(eta is not None and eta < 1.15),
                        "source": str(metrics.get("source") or "google"),
                    }
                )
            except Exception:
                # keep context resilient; skip noisy route-level failures
                continue
            if len(active_routes) >= 8:
                break

        summary = await self._finance.financial_summary(empresa_id=eid)
        unpaid = await self._facturas.list_facturas(empresa_id=eid)
        today = date.today()
        open_days: list[int] = []
        for inv in unpaid:
            if str(inv.estado_cobro or "").strip().lower() == "cobrada":
                continue
            if inv.fecha_emision:
                open_days.append(max(0, (today - inv.fecha_emision).days))
        dso_days = round(sum(open_days) / len(open_days), 2) if open_days else 0.0

        # VerifactuModule mapping: chain audit over tenant invoices.
        vf_res = await db.execute(
            db.table("facturas")
            .select(
                "id,cliente,numero_factura,num_factura,fecha_emision,nif_emisor,total_factura,"
                "fingerprint_hash,previous_fingerprint"
            )
            .eq("empresa_id", eid)
            .order("fecha_emision", desc=False)
            .limit(200)
        )
        vf_rows: list[dict[str, Any]] = (vf_res.data or []) if hasattr(vf_res, "data") else []
        vf_nif_map = await load_cliente_nif_map_for_facturas(db, empresa_id=eid, rows=vf_rows)
        vf_rows_m = materialize_factura_rows_for_fingerprint_verify(
            vf_rows, cliente_nif_map=vf_nif_map
        )
        vf_report = verify_invoice_chain(vf_rows_m)

        payload = {
            "operational": {
                "cpk_eur": float(COSTE_OPERATIVO_EUR_KM),
                "active_routes": active_routes,
                "routes_count": len(active_routes),
                "vampire_routes_count": len([r for r in active_routes if r.get("vampire_route")]),
                "total_emisiones_co2_kg": round(total_emisiones_co2_kg, 2),
            },
            "financial": {
                "ingresos_netos_sin_iva_eur": round(float(summary.ingresos), 2),
                "gastos_netos_sin_iva_eur": round(float(summary.gastos), 2),
                "ebitda_aprox_sin_iva_eur": round(float(summary.ebitda), 2),
                "dso_days": dso_days,
                "liquidity_risk": bool(dso_days > 60),
            },
            "fiscal": {
                "verifactu_chain_ok": bool(vf_report.get("is_valid", False)),
                "verifactu_total_invoices": len(vf_rows_m),
                "verifactu_issues": 0
                if vf_report.get("is_valid")
                else 1,
            },
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    async def build_data_context(self, *, empresa_id: str) -> dict[str, Any]:
        eid = str(empresa_id or "").strip()
        if not eid:
            return {
                "current_portes": [],
                "financial_summary": {},
                "maps_data": {},
            }

        dashboard = await self._finance.financial_dashboard(empresa_id=eid)
        ai_snapshot_min = await self.prepare_ai_context(empresa_id=eid)
        ai_snapshot = json.loads(ai_snapshot_min)
        operational = ai_snapshot.get("operational") or {}
        financial = ai_snapshot.get("financial") or {}

        current_portes: list[dict[str, Any]] = []
        maps_routes = operational.get("active_routes") or []
        for row in maps_routes:
            current_portes.append(
                {
                    "route_ref": row.get("route_ref"),
                    "income_eur": row.get("income_eur"),
                    "km_estimados": row.get("distance_km"),
                    "emisiones_co2_kg": row.get("emisiones_co2_kg"),
                    "estado": "activo",
                }
            )

        financial_summary = {
            "ingresos_netos_sin_iva_eur": financial.get("ingresos_netos_sin_iva_eur"),
            "gastos_netos_sin_iva_eur": financial.get("gastos_netos_sin_iva_eur"),
            "ebitda_aprox_sin_iva_eur": financial.get("ebitda_aprox_sin_iva_eur"),
            "margen_neto_por_km_mes_actual": dashboard.margen_neto_km_mes_actual,
            "dso_days": financial.get("dso_days"),
            "liquidity_risk": bool(financial.get("liquidity_risk")),
        }

        return {
            "current_portes": current_portes,
            "financial_summary": financial_summary,
            "maps_data": {
                "cpk_used": operational.get("cpk_eur", float(COSTE_OPERATIVO_EUR_KM)),
                "total_emisiones_co2_kg": operational.get("total_emisiones_co2_kg"),
                "routes_analyzed": maps_routes,
            },
            "fiscal_data": ai_snapshot.get("fiscal") or {},
        }

    @staticmethod
    def _token_overlap_score(blob: str, sample: str) -> float:
        """Similitud léxica conservadora entre conceptos bancarios (sin PII estructurada)."""
        btoks = {
            t
            for t in re.findall(r"[a-záéíóúñ0-9]{3,}", (blob or "").casefold())
            if len(t) >= 3
        }
        stoks = {
            t
            for t in re.findall(r"[a-záéíóúñ0-9]{3,}", (sample or "").casefold())
            if len(t) >= 3
        }
        if not btoks or not stoks:
            return 0.0
        inter = len(btoks & stoks)
        return min(1.0, float(inter) / float(max(len(btoks), 1)))

    async def score_bank_invoice_match_from_client_history(
        self,
        *,
        empresa_id: str,
        transaction: Transaccion,
        candidates: list[ConciliationCandidate],
    ) -> tuple[int | None, float, str]:
        """
        Puntuación de confianza usando **historial de cobros** del cliente (facturas cobradas con
        ``matched_transaction_id`` y textos de ``bank_transactions`` asociados).

        Devuelve ``(factura_id, score 0–1, nota)``; ``(None, …)`` si no hay señal suficientemente clara.
        """
        eid = str(empresa_id or "").strip()
        if not eid or not candidates:
            return None, 0.0, "sin contexto"
        db = self._flota._db  # type: ignore[attr-defined]

        blob = transaction.reference_blob()
        ranked: list[tuple[int, float, str]] = []

        for c in candidates[:5]:
            res_f: Any = await db.execute(
                db.table("facturas")
                .select("id, cliente, numero_factura, num_factura")
                .eq("empresa_id", eid)
                .eq("id", int(c.factura_id))
                .limit(1)
            )
            fr = (res_f.data or []) if hasattr(res_f, "data") else []
            if not fr:
                continue
            row = dict(fr[0])
            cliente_id = str(row.get("cliente") or "").strip()
            inv_no = str(row.get("numero_factura") or row.get("num_factura") or "").strip()
            inv_cf = inv_no.casefold()
            blob_cf = blob.casefold()

            hist_overlap = 0.0
            if cliente_id:
                try:
                    res_hist: Any = await db.execute(
                        db.table("facturas")
                        .select("matched_transaction_id")
                        .eq("empresa_id", eid)
                        .eq("cliente", cliente_id)
                        .eq("estado_cobro", "cobrada")
                        .not_.is_("matched_transaction_id", "null")
                        .order("id", desc=True)
                        .limit(40)
                    )
                    mids: list[str] = []
                    for h in (res_hist.data or []) if hasattr(res_hist, "data") else []:
                        mid = str(h.get("matched_transaction_id") or "").strip()
                        if mid and mid not in mids:
                            mids.append(mid)
                    if mids:
                        res_bt: Any = await db.execute(
                            db.table("bank_transactions")
                            .select("description, remittance_info")
                            .eq("empresa_id", eid)
                            .in_("transaction_id", mids[:45])
                        )
                        for bt in (res_bt.data or []) if hasattr(res_bt, "data") else []:
                            desc = f"{bt.get('description') or ''} {bt.get('remittance_info') or ''}"
                            hist_overlap = max(hist_overlap, self._token_overlap_score(blob, desc))
                except Exception:
                    hist_overlap = 0.0

            inv_hit = 1.0 if inv_cf and inv_cf in blob_cf else 0.0
            hist_score = min(
                1.0,
                0.42 * hist_overlap + 0.33 * inv_hit + 0.25 * float(c.reference_score),
            )
            note = (
                f"LogisAdvisor: hist_overlap={hist_overlap:.2f}, ref_factura={inv_hit:.2f}, "
                f"fuzzy_ref={float(c.reference_score):.2f}"
            )
            ranked.append((int(c.factura_id), float(hist_score), note))

        if not ranked:
            return None, 0.0, "sin candidatos válidos"
        ranked.sort(key=lambda x: -x[1])
        best_id, best_s, best_note = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        if best_s < 0.58:
            return None, best_s, best_note + " (umbral no alcanzado)"
        if best_s - second < 0.07 and len(ranked) > 1:
            return None, best_s, "empate entre candidatos; requiere revisión"
        return best_id, round(best_s, 4), best_note

    async def generate_diagnostic(
        self,
        *,
        data_context: dict[str, Any],
        user_query: str,
    ) -> dict[str, Any]:
        if not self.openai_configured():
            raise RuntimeError("No hay credenciales IA configuradas (OpenAI o Gemini).")

        model = self.model_name()
        payload = {
            "current_portes": data_context.get("current_portes") or [],
            "financial_summary": data_context.get("financial_summary") or {},
            "maps_data": data_context.get("maps_data") or {},
        }
        prompt = (
            f"{LOGISADVISOR_CONTEXT}\n\n"
            "User Query:\n"
            f"{(user_query or '').strip()}\n\n"
            "Data Context JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False)}\n\n"
            "Return a JSON object with keys: "
            "profitability, fiscal_safety, liquidity, summary_headline, risk_flags, recommended_actions. "
            "Each of profitability/fiscal_safety/liquidity must include: status, findings (array), actions (array)."
        )
        response = await litellm.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": "You are a senior logistics and fiscal advisor."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.25,
        )
        content = ""
        choices = getattr(response, "choices", None) or []
        if choices:
            msg = getattr(choices[0], "message", None)
            content = str(getattr(msg, "content", "") or "").strip()
        parsed: dict[str, Any]
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {
                "summary_headline": "Diagnóstico generado",
                "profitability": {"status": "warning", "findings": [content], "actions": []},
                "fiscal_safety": {"status": "info", "findings": [], "actions": []},
                "liquidity": {"status": "info", "findings": [], "actions": []},
                "risk_flags": [],
                "recommended_actions": [],
            }
        parsed["model"] = model
        parsed["data_context"] = payload
        return parsed

    async def _get_financial_summary(self, *, empresa_id: str) -> str:
        eid = str(empresa_id or "").strip()
        s = await self._finance.financial_summary(empresa_id=eid)
        d = await self._finance.financial_dashboard(empresa_id=eid)
        payload = {
            "ingresos_netos_sin_iva_eur": round(s.ingresos, 2),
            "gastos_netos_sin_iva_eur": round(s.gastos, 2),
            "ebitda_aprox_sin_iva_eur": round(s.ebitda, 2),
            "km_totales_estimados_facturas": d.total_km_estimados_snapshot,
            "margen_ebitda_por_km_eur": d.margen_km_eur,
            "margen_neto_por_km_mes_actual": d.margen_neto_km_mes_actual,
            "margen_neto_por_km_mes_anterior": d.margen_neto_km_mes_anterior,
            "variacion_margen_km_pct": d.variacion_margen_km_pct,
            "km_facturados_mes_actual": d.km_facturados_mes_actual,
            "km_facturados_mes_anterior": d.km_facturados_mes_anterior,
            "serie_6_meses": [
                {"periodo": x.periodo, "ingresos": x.ingresos, "gastos": x.gastos}
                for x in (d.ingresos_vs_gastos_mensual or [])[-6:]
            ],
        }
        return json.dumps(payload, ensure_ascii=False)

    async def _get_unpaid_invoices(self, *, empresa_id: str) -> str:
        eid = str(empresa_id or "").strip()
        rows = await self._facturas.list_facturas(empresa_id=eid)
        unpaid: list[dict[str, Any]] = []
        for f in rows:
            st = (f.estado_cobro or "").strip().lower()
            if st == "cobrada":
                continue
            nombre = None
            if f.cliente_detalle and f.cliente_detalle.nombre:
                nombre = str(f.cliente_detalle.nombre).strip()[:120]
            unpaid.append(
                {
                    "numero_factura": f.numero_factura,
                    "fecha_emision": f.fecha_emision.isoformat(),
                    "total_factura_eur": round(float(f.total_factura), 2),
                    "estado_cobro": f.estado_cobro or "—",
                    "cliente_nombre": nombre,
                }
            )
        unpaid.sort(key=lambda x: x.get("fecha_emision") or "", reverse=True)
        return json.dumps(
            {"facturas_no_cobradas": unpaid[:80], "total": len(unpaid)},
            ensure_ascii=False,
        )

    async def _get_fleet_efficiency_metrics(self, *, empresa_id: str) -> str:
        eid = str(empresa_id or "").strip()
        hoy = date.today()
        m, y = hoy.month, hoy.year
        if m == 1:
            m, y = 12, y - 1
        else:
            m -= 1

        fleet = await self._flota.metricas_flota(empresa_id=eid)
        dash = await self._finance.financial_dashboard(empresa_id=eid)

        maps_info = {
            "distance_matrix_configurado": bool(self._maps.maps_api_key()),
            "nota": "Las distancias de ruta usan Google Distance Matrix cuando está configurado; "
            "la huella CO₂ reutiliza esas distancias vía ESG.",
        }

        esg_block: dict[str, Any]
        try:
            huella = await self._esg.calcular_huella_carbono_mensual(empresa_id=eid, mes=m, anio=y)
            co2_km = None
            if huella.total_km_reales and huella.total_km_reales > 0:
                co2_km = round(float(huella.total_co2_kg) / float(huella.total_km_reales), 6)
            top_v = []
            for v in (huella.por_vehiculo or [])[:8]:
                top_v.append(
                    {
                        "matricula": v.matricula,
                        "etiqueta": (v.etiqueta or "")[:80],
                        "co2_kg": v.co2_kg,
                        "km_reales": v.km_reales,
                    }
                )
            esg_block = {
                "periodo_calendario": f"{y}-{m:02d}",
                "total_co2_kg": huella.total_co2_kg,
                "km_reales_rutas": huella.total_km_reales,
                "co2_kg_por_km": co2_km,
                "portes_facturados_en_periodo": huella.num_portes_facturados,
                "top_vehiculos_co2": top_v,
            }
        except Exception as ex:
            logger.info("ESG/huella no disponible para LogisAdvisor: %s", ex)
            esg_block = {
                "disponible": False,
                "motivo": "No se pudo calcular la huella (datos o configuración).",
            }

        payload = {
            "flota": {
                "total_vehiculos": fleet.total_vehiculos,
                "disponibles": fleet.disponibles,
                "en_riesgo_parada": fleet.en_riesgo_parada,
                "pct_disponible": fleet.pct_disponible,
                "pct_riesgo_parada": fleet.pct_riesgo_parada,
            },
            "finanzas_operativas": {
                "margen_neto_por_km_mes_actual": dash.margen_neto_km_mes_actual,
                "km_facturados_mes_actual": dash.km_facturados_mes_actual,
                "margen_ebitda_por_km_eur": dash.margen_km_eur,
            },
            "maps": maps_info,
            "esg_huella_mes_anterior": esg_block,
        }
        return json.dumps(payload, ensure_ascii=False)

    async def _dispatch_tool(self, *, name: str, empresa_id: str) -> str:
        if name == "get_financial_summary":
            return await self._get_financial_summary(empresa_id=empresa_id)
        if name == "get_unpaid_invoices":
            return await self._get_unpaid_invoices(empresa_id=empresa_id)
        if name == "get_fleet_efficiency_metrics":
            return await self._get_fleet_efficiency_metrics(empresa_id=empresa_id)
        return json.dumps({"error": f"Herramienta desconocida: {name}"}, ensure_ascii=False)

    async def chat(
        self,
        *,
        empresa_id: str,
        user_message: str,
        history: list[dict[str, str]],
    ) -> tuple[str, str | None]:
        """
        Devuelve (respuesta_markdown, modelo_usado).

        ``history`` es lista de {"role": "user"|"assistant", "content": "..."} (últimos turnos).
        """
        from openai import AsyncOpenAI

        if not self.openai_configured():
            raise RuntimeError("OPENAI_API_KEY no configurada")

        api_key = get_secret_manager().get_openai_api_key()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY no configurada (se requiere para el cliente OpenAI)")
        client = AsyncOpenAI(api_key=api_key)
        model = self.model_name()
        tools = _tool_specs()

        # Últimos mensajes para contexto breve
        hist_trim = history[-12:] if history else []
        messages: list[dict[str, Any]] = [{"role": "system", "content": LOGIS_ADVISOR_SYSTEM_PROMPT}]
        messages.append(
            {
                "role": "system",
                "content": (
                    f"Contexto de sesión: empresa_id del tenant (solo referencia interna; no lo repitas literalmente "
                    f"salvo que sea útil como etiqueta): {empresa_id[:8]}…"
                ),
            }
        )
        for m in hist_trim:
            r = m.get("role")
            c = m.get("content")
            if r in ("user", "assistant") and c and str(c).strip():
                messages.append({"role": r, "content": str(c).strip()})
        messages.append({"role": "user", "content": user_message.strip()})

        max_rounds = 8
        for _ in range(max_rounds):
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.35,
            )
            choice = response.choices[0]
            msg = choice.message

            if msg.tool_calls:
                messages.append(msg.model_dump(exclude_none=True))
                for tc in msg.tool_calls:
                    fname = tc.function.name
                    try:
                        tool_text = await self._dispatch_tool(name=fname, empresa_id=empresa_id)
                    except Exception as ex:
                        logger.exception("LogisAdvisor tool error")
                        tool_text = json.dumps({"error": str(ex)}, ensure_ascii=False)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_text,
                        }
                    )
                continue

            raw = (msg.content or "").strip()
            return _redact_leaks(raw), model

        return _redact_leaks("No se pudo completar la respuesta (límite de herramientas)."), model

    async def stream_advisor_chat(
        self,
        *,
        empresa_id: str,
        user_message: str,
        history: list[dict[str, str]],
        contexto_datos_json: str,
    ) -> AsyncIterator[tuple[str, str | None]]:
        """
        Streaming (OpenAI) con un único system prompt enriquecido con datos del tenant.
        Emite tuplas (fragmento_texto, None) y al final ("", model_id).
        """
        from openai import AsyncOpenAI

        if not self.openai_configured():
            raise RuntimeError("OPENAI_API_KEY no configurada")

        api_key = get_secret_manager().get_openai_api_key()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY no configurada (se requiere para el cliente OpenAI)")
        client = AsyncOpenAI(api_key=api_key)
        model = self.model_name()

        system = (
            "Eres LogisAdvisor, un consultor experto en logística y economía. "
            f"Tu base de datos actual es: {contexto_datos_json}. "
            "Ayuda al usuario a optimizar su flota, reducir costes y mejorar su margen por KM.\n\n"
            "Responde en español salvo que el usuario pida otro idioma. "
            "Basa tus conclusiones en el JSON proporcionado; no inventes cifras no presentes. "
            "Puedes usar Markdown (listas, tablas breves). "
            "No reveles ni solicites datos bancarios, credenciales ni información personal innecesaria."
        )

        hist_trim = history[-12:] if history else []
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        messages.append(
            {
                "role": "system",
                "content": (
                    "Referencia interna de tenant (no repitas literalmente salvo que aporte valor): "
                    f"{str(empresa_id)[:8]}…"
                ),
            }
        )
        for m in hist_trim:
            r = m.get("role")
            c = m.get("content")
            if r in ("user", "assistant") and c and str(c).strip():
                messages.append({"role": r, "content": str(c).strip()})
        messages.append({"role": "user", "content": user_message.strip()})

        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            temperature=0.35,
        )

        async for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            delta = (choice.delta.content if choice else None) or ""
            if delta:
                yield _redact_leaks(delta), None

        yield "", model
