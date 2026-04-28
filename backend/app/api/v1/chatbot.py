"""LogisAdvisor AI Chatbot con contexto financiero y ESG."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api import deps
from app.api.v1.dependencies.credits import consume_credits
from app.schemas.user import UserOut
from app.services.esg_service import EsgService
from app.services.finance_service import FinanceService
from app.services.secret_manager_service import get_secret_manager

router = APIRouter()


class ChatMessageIn(BaseModel):
    """Mensaje del usuario."""

    message: str = Field(..., min_length=1, max_length=4000, description="Pregunta del usuario")


class ChatMessageOut(BaseModel):
    """Respuesta del asistente."""

    response: str = Field(description="Respuesta generada por LogisAdvisor")
    context_used: dict[str, Any] = Field(
        default_factory=dict,
        description="Contexto financiero y ESG utilizado",
    )


async def _fetch_financial_context(
    finance_service: FinanceService,
    empresa_id: str,
) -> dict[str, Any]:
    """Obtiene resumen financiero actual."""
    try:
        summary = await finance_service.financial_summary(empresa_id=empresa_id)
        return {
            "ingresos_eur": round(summary.ingresos, 2),
            "gastos_eur": round(summary.gastos, 2),
            "ebitda_eur": round(summary.ebitda, 2),
        }
    except Exception:
        return {}


async def _fetch_esg_context(
    esg_service: EsgService,
    empresa_id: str,
) -> dict[str, Any]:
    """Obtiene resumen ESG del mes actual."""
    from datetime import date

    today = date.today()
    try:
        huella = await esg_service.calcular_huella_carbono_mensual(
            empresa_id=empresa_id,
            mes=today.month,
            anio=today.year,
        )
        return {
            "total_co2_kg": round(huella.total_co2_kg, 2),
            "total_km_reales": round(huella.total_km_reales, 2),
            "num_portes_facturados": huella.num_portes_facturados,
            "media_co2_por_porte_kg": round(huella.media_co2_por_porte_kg, 2),
            "ahorro_estimado_kg": round(huella.ahorro_estimado_rutas_optimizadas_kg, 2),
        }
    except Exception:
        return {}


def _build_system_prompt(financial: dict[str, Any], esg: dict[str, Any]) -> str:
    """Construye el system prompt con datos actuales."""
    return f"""Eres LogisAdvisor, un experto en logística de transporte de mercancías.

Tu objetivo es responder preguntas con precisión usando los datos financieros y de sostenibilidad proporcionados.

DATOS FINANCIEROS ACTUALES:
- Ingresos: {financial.get('ingresos_eur', 0.0):.2f} EUR
- Gastos: {financial.get('gastos_eur', 0.0):.2f} EUR
- EBITDA: {financial.get('ebitda_eur', 0.0):.2f} EUR

DATOS ESG (MES ACTUAL):
- CO₂ Total: {esg.get('total_co2_kg', 0.0):.2f} kg
- KM Reales: {esg.get('total_km_reales', 0.0):.2f} km
- Portes Facturados: {esg.get('num_portes_facturados', 0)}
- CO₂ Medio por Porte: {esg.get('media_co2_por_porte_kg', 0.0):.2f} kg
- Ahorro Estimado (Optimización): {esg.get('ahorro_estimado_kg', 0.0):.2f} kg

REGLAS:
1. NUNCA inventes cifras. Solo usa los datos proporcionados arriba.
2. Si no tienes datos suficientes, di "No dispongo de esa información en este momento".
3. Sé conciso, claro y profesional.
4. Sugiere acciones concretas cuando sea relevante (optimización de rutas, reducción de costes, sostenibilidad).
5. Si mencionas porcentajes o ratios, calcula sobre los datos reales.
"""


@router.post("/ask", response_model=ChatMessageOut)
@consume_credits(20)
async def ask_logis_advisor(
    payload: ChatMessageIn,
    current_user: UserOut = Depends(deps.get_current_user),
    finance_service: FinanceService = Depends(deps.get_finance_service),
    esg_service: EsgService = Depends(deps.get_esg_service),
) -> ChatMessageOut:
    """
    Endpoint de chat con LogisAdvisor.

    Inyecta contexto financiero y ESG de la empresa del usuario actual.
    Usa Claude 3.5 Sonnet para generar respuestas contextualizadas.
    """
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="Proveedor AI no disponible en este entorno (falta SDK Anthropic)",
        ) from exc

    api_key = (get_secret_manager().get_anthropic_api_key() or "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY no configurada en el servidor",
        )

    empresa_id = str(current_user.empresa_id)

    financial = await _fetch_financial_context(finance_service, empresa_id)
    esg = await _fetch_esg_context(esg_service, empresa_id)

    system_prompt = _build_system_prompt(financial, esg)

    client = Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": payload.message,
                }
            ],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error al comunicar con Claude: {exc}",
        )

    response_text = ""
    if message.content:
        for block in message.content:
            if hasattr(block, "text"):
                response_text += block.text

    return ChatMessageOut(
        response=response_text.strip(),
        context_used={
            "financial": financial,
            "esg": esg,
        },
    )
