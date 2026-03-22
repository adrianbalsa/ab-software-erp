from __future__ import annotations

import json
import logging
import os
import re
from datetime import date
from typing import Any

from app.services.esg_service import EsgService
from app.services.facturas_service import FacturasService
from app.services.finance_service import FinanceService
from app.services.flota_service import FlotaService
from app.services.maps_service import MapsService

logger = logging.getLogger(__name__)

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
        return bool((os.getenv("OPENAI_API_KEY") or "").strip())

    @staticmethod
    def model_name() -> str:
        return (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()

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

        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
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
