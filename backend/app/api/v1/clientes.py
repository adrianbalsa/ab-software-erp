from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.api import deps
from app.db.supabase import SupabaseAsync
from app.schemas.user import UserOut
from app.services.clientes_service import ClientesService

router = APIRouter()

_EMAIL_ADAPTER = TypeAdapter(EmailStr)

_STATE_PENDING_RISK = "PENDING_RISK"
_STATE_PENDING_SEPA = "PENDING_SEPA"
_STATE_ACTIVE = "ACTIVE"


def _extract_supabase_error_status(exc: Exception) -> int | None:
    for key in ("status_code", "status", "code"):
        raw = getattr(exc, key, None)
        if raw is None:
            continue
        try:
            code = int(raw)
        except (TypeError, ValueError):
            continue
        if 100 <= code <= 599:
            return code
    return None


def _is_supabase_bad_request(exc: Exception) -> bool:
    status_code = _extract_supabase_error_status(exc)
    if status_code is not None:
        return 400 <= status_code < 500
    text = str(exc or "").lower()
    markers = (
        "already registered",
        "already exists",
        "invalid email",
        "email rate limit",
        "unprocessable",
        "bad request",
    )
    return any(m in text for m in markers)


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in {"1", "true", "t", "yes", "si"}


def _cliente_onboarding_state(row: dict[str, Any]) -> str:
    mandato_activo = _to_bool(row.get("mandato_activo"))
    riesgo_aceptado = _to_bool(row.get("riesgo_aceptado"))
    if mandato_activo:
        return _STATE_ACTIVE
    if riesgo_aceptado:
        return _STATE_PENDING_SEPA
    return _STATE_PENDING_RISK


@router.post(
    "/{cliente_id}/invitar",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Invitar cliente B2B al portal",
)
async def invite_cliente_b2b(
    cliente_id: UUID,
    _: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    current_user: UserOut = Depends(deps.bind_write_context),
    db: SupabaseAsync = Depends(deps.get_db),
) -> dict[str, str]:
    empresa_id = str(current_user.empresa_id)
    cid = str(cliente_id)

    res_cliente: Any = await db.execute(
        db.table("clientes")
        .select("id,empresa_id,email,fecha_invitacion")
        .eq("id", cid)
        .eq("empresa_id", empresa_id)
        .limit(1)
    )
    cli_rows: list[dict[str, Any]] = (res_cliente.data or []) if hasattr(res_cliente, "data") else []
    if not cli_rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
    cliente = cli_rows[0]

    email = str(cliente.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El cliente no tiene un email válido",
        )
    try:
        _EMAIL_ADAPTER.validate_python(email)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El cliente no tiene un email válido",
        ) from exc

    res_profile: Any = await db.execute(
        db.table("profiles")
        .select("id")
        .eq("cliente_id", cid)
        .limit(1)
    )
    prof_rows: list[dict[str, Any]] = (res_profile.data or []) if hasattr(res_profile, "data") else []
    if prof_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El cliente ya está registrado",
        )

    try:
        await db.auth_admin_invite_user_by_email(
            email=email,
            options={
                "data": {
                    "empresa_id": empresa_id,
                    "cliente_id": cid,
                    "rbac_role": "cliente",
                }
            },
        )
    except Exception as exc:
        detail = str(exc).strip() or "Error al enviar la invitación con Supabase Auth"
        if _is_supabase_bad_request(exc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from exc

    invited_at = datetime.now(timezone.utc).isoformat()
    try:
        await db.execute(
            db.table("clientes")
            .update({"fecha_invitacion": invited_at})
            .eq("id", cid)
            .eq("empresa_id", empresa_id)
        )
    except Exception:
        # Compatibilidad: si el campo no existe todavía no bloqueamos la invitación.
        pass

    await db.execute(
        db.table("audit_logs").insert(
            {
                "empresa_id": empresa_id,
                "table_name": "clientes",
                "record_id": cid,
                "action": "INVITE_SENT",
                "old_data": {"fecha_invitacion": cliente.get("fecha_invitacion")},
                "new_data": {
                    "fecha_invitacion": invited_at,
                    "invite_email": email,
                    "invite_channel": "supabase_auth_admin",
                },
                "changed_by": str(current_user.usuario_id) if current_user.usuario_id else None,
            }
        )
    )

    return {
        "status": "ok",
        "detail": "Invitación enviada correctamente",
    }


@router.get(
    "/onboarding-dashboard",
    summary="Dashboard de onboarding comercial y riesgo por cliente",
)
async def onboarding_dashboard(
    _: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    current_user: UserOut = Depends(deps.get_current_user),
    db: SupabaseAsync = Depends(deps.get_db),
) -> dict[str, Any]:
    empresa_id = str(current_user.empresa_id)

    # Intento completo (esquema actualizado) con fallback para compatibilidad.
    rows: list[dict[str, Any]] = []
    try:
        res: Any = await db.execute(
            db.table("clientes")
            .select("id,nombre,email,limite_credito,fecha_invitacion,riesgo_aceptado,mandato_activo,deleted_at,is_blocked")
            .eq("empresa_id", empresa_id)
            .is_("deleted_at", "null")
        )
        rows = (res.data or []) if hasattr(res, "data") else []
    except Exception:
        res_fallback: Any = await db.execute(
            db.table("clientes")
            .select("id,nombre,email,riesgo_aceptado,mandato_activo,deleted_at")
            .eq("empresa_id", empresa_id)
            .is_("deleted_at", "null")
        )
        rows = (res_fallback.data or []) if hasattr(res_fallback, "data") else []

    total_clientes = len(rows)
    pendientes_riesgo = 0
    pendientes_sepa = 0
    operativos = 0
    clientes: list[dict[str, Any]] = []

    for row in rows:
        riesgo_aceptado = _to_bool(row.get("riesgo_aceptado"))
        mandato_activo = _to_bool(row.get("mandato_activo"))
        fecha_invitacion = row.get("fecha_invitacion")
        estado = _cliente_onboarding_state(row)

        if mandato_activo:
            operativos += 1
        elif riesgo_aceptado:
            pendientes_sepa += 1
        elif fecha_invitacion is not None:
            pendientes_riesgo += 1

        limite_credito = row.get("limite_credito")
        try:
            limite_credito_num = float(limite_credito) if limite_credito is not None else 3000.0
        except (TypeError, ValueError):
            limite_credito_num = 3000.0

        clientes.append(
            {
                "id": str(row.get("id") or ""),
                "nombre": str(row.get("nombre") or ""),
                "email": str(row.get("email") or ""),
                "limite_credito": limite_credito_num,
                "estado": estado,
                "fecha_invitacion": fecha_invitacion,
                "riesgo_aceptado": riesgo_aceptado,
                "mandato_activo": mandato_activo,
                "is_blocked": _to_bool(row.get("is_blocked")),
            }
        )

    return {
        "summary": {
            "total_clientes": total_clientes,
            "pendientes_riesgo": pendientes_riesgo,
            "pendientes_sepa": pendientes_sepa,
            "operativos": operativos,
        },
        "clientes": clientes,
    }


@router.post(
    "/{cliente_id}/resend-invite",
    status_code=status.HTTP_200_OK,
    summary="Reenviar invitación de onboarding a cliente pendiente",
)
async def resend_onboarding_invite(
    cliente_id: UUID,
    _: UserOut = Depends(deps.require_role("owner")),
    current_user: UserOut = Depends(deps.bind_write_context),
    clientes_service: ClientesService = Depends(deps.get_clientes_service),
) -> dict[str, str]:
    return await clientes_service.resend_onboarding_invite(
        cliente_id=str(cliente_id),
        empresa_id=str(current_user.empresa_id),
    )

