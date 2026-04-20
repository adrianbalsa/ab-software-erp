from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from starlette.requests import Request
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.api import deps
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.user import UserOut
from app.services.audit_logs_service import AuditLogsService
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


def _parse_date_only(val: object) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if len(s) >= 10:
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None
    return None


def _last_n_month_keys(n: int) -> list[str]:
    today = date.today()
    y, m = today.year, today.month
    keys: list[str] = []
    for _ in range(n):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(keys))


def _cliente_ui_status(
    *,
    is_blocked: bool,
    riesgo_aceptado: bool,
    mandato_activo: bool,
    saldo_pendiente: float,
    limite_credito: float,
) -> str:
    if is_blocked:
        return "inactivo"
    if riesgo_aceptado and mandato_activo:
        if limite_credito > 0:
            if saldo_pendiente / limite_credito >= 0.85:
                return "riesgo"
        elif saldo_pendiente > 0:
            return "riesgo"
        return "activo"
    if riesgo_aceptado and not mandato_activo:
        return "riesgo"
    return "inactivo"


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
    audit_logs: AuditLogsService = Depends(deps.get_audit_logs_service),
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

    await audit_logs.log_sensitive_action(
        empresa_id=empresa_id,
        table_name="clientes",
        record_id=cid,
        action="INVITE_SENT",
        old_value={"fecha_invitacion": cliente.get("fecha_invitacion")},
        new_value={
            "fecha_invitacion": invited_at,
            "invite_email": email,
            "invite_channel": "supabase_auth_admin",
        },
        user_id=current_user.usuario_id,
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


@router.get(
    "/{cliente_id}/detail",
    summary="Ficha operativa del cliente (KPIs, portes recientes, tendencia de facturación)",
)
async def cliente_operational_detail(
    cliente_id: UUID,
    _: UserOut = Depends(deps.require_role("owner", "traffic_manager")),
    current_user: UserOut = Depends(deps.get_current_user),
    db: SupabaseAsync = Depends(deps.get_db),
) -> dict[str, Any]:
    empresa_id = str(current_user.empresa_id)
    cid = str(cliente_id)

    res_cli: Any = await db.execute(
        db.table("clientes")
        .select("id,nombre,email,limite_credito,riesgo_aceptado,mandato_activo,is_blocked,deleted_at")
        .eq("empresa_id", empresa_id)
        .eq("id", cid)
        .limit(1)
    )
    cli_rows: list[dict[str, Any]] = (res_cli.data or []) if hasattr(res_cli, "data") else []
    if not cli_rows or cli_rows[0].get("deleted_at") is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")

    cli = cli_rows[0]
    riesgo_aceptado = _to_bool(cli.get("riesgo_aceptado"))
    mandato_activo = _to_bool(cli.get("mandato_activo"))
    is_blocked = _to_bool(cli.get("is_blocked"))
    try:
        limite_credito = float(cli.get("limite_credito") if cli.get("limite_credito") is not None else 3000.0)
    except (TypeError, ValueError):
        limite_credito = 3000.0

    res_fac: Any = await db.execute(
        db.table("facturas")
        .select("id,total_factura,fecha_emision,estado_cobro,fecha_cobro_real")
        .eq("empresa_id", empresa_id)
        .eq("cliente", cid)
    )
    facturas: list[dict[str, Any]] = (res_fac.data or []) if hasattr(res_fac, "data") else []

    total_facturado = 0.0
    saldo_pendiente = 0.0
    dias_pago_muestras: list[int] = []
    month_totals: dict[str, float] = {}
    month_keys = _last_n_month_keys(6)
    for mk in month_keys:
        month_totals[mk] = 0.0

    for fr in facturas:
        try:
            tot = float(fr.get("total_factura") or 0.0)
        except (TypeError, ValueError):
            tot = 0.0
        total_facturado += tot
        st = str(fr.get("estado_cobro") or "").strip().lower()
        if st != "cobrada":
            saldo_pendiente += max(0.0, tot)
        em = _parse_date_only(fr.get("fecha_emision"))
        fc = _parse_date_only(fr.get("fecha_cobro_real"))
        if st == "cobrada" and em and fc:
            dias_pago_muestras.append(max(0, (fc - em).days))

        mk = None
        raw_fe = fr.get("fecha_emision")
        if raw_fe is not None:
            sfe = str(raw_fe).strip()
            if len(sfe) >= 7 and sfe[4] == "-":
                mk = sfe[:7]
        if mk in month_totals:
            month_totals[mk] += tot

    dias_pago_promedio: float | None = None
    if dias_pago_muestras:
        dias_pago_promedio = round(sum(dias_pago_muestras) / len(dias_pago_muestras), 1)

    res_portes: Any = await db.execute(
        filter_not_deleted(
            db.table("portes")
            .select("id,origen,destino,fecha,estado,fecha_entrega_real")
            .eq("empresa_id", empresa_id)
            .eq("cliente_id", cid)
        )
    )
    porte_rows: list[dict[str, Any]] = (res_portes.data or []) if hasattr(res_portes, "data") else []
    portes_count = len(porte_rows)

    def _porte_sort_ts(r: dict[str, Any]) -> str:
        return str(r.get("fecha_entrega_real") or r.get("fecha") or "")

    porte_rows_sorted = sorted(porte_rows, key=_porte_sort_ts, reverse=True)[:10]

    portes_recientes: list[dict[str, Any]] = []
    for pr in porte_rows_sorted:
        fer = pr.get("fecha_entrega_real")
        fe = pr.get("fecha")
        portes_recientes.append(
            {
                "id": str(pr.get("id") or ""),
                "origen": str(pr.get("origen") or ""),
                "destino": str(pr.get("destino") or ""),
                "fecha": fe,
                "estado": str(pr.get("estado") or ""),
                "fecha_entrega_real": fer,
            }
        )

    facturacion_mensual = [{"mes": mk, "total_facturado": round(month_totals.get(mk, 0.0), 2)} for mk in month_keys]

    estado_ui = _cliente_ui_status(
        is_blocked=is_blocked,
        riesgo_aceptado=riesgo_aceptado,
        mandato_activo=mandato_activo,
        saldo_pendiente=saldo_pendiente,
        limite_credito=limite_credito,
    )

    return {
        "cliente": {
            "id": cid,
            "nombre": str(cli.get("nombre") or ""),
            "email": str(cli.get("email") or ""),
            "limite_credito": limite_credito,
            "riesgo_aceptado": riesgo_aceptado,
            "mandato_activo": mandato_activo,
            "is_blocked": is_blocked,
            "estado_ui": estado_ui,
        },
        "metricas": {
            "total_facturado": round(total_facturado, 2),
            "portes_realizados": portes_count,
            "dias_pago_promedio": dias_pago_promedio,
        },
        "facturacion_mensual": facturacion_mensual,
        "portes_recientes": portes_recientes,
    }


@router.post(
    "/{cliente_id}/resend-invite",
    status_code=status.HTTP_200_OK,
    summary="Reenviar invitación de onboarding a cliente pendiente",
)
async def resend_onboarding_invite(
    request: Request,
    background_tasks: BackgroundTasks,
    cliente_id: UUID,
    _: UserOut = Depends(deps.require_role("owner")),
    current_user: UserOut = Depends(deps.bind_write_context),
    clientes_service: ClientesService = Depends(deps.get_clientes_service),
) -> dict[str, str]:
    request.state.audit_payload_supplement = {
        "delegado_segundo_plano": True,
        "operacion": "onboarding_invite_resend",
        "mensaje": "Email encolado para envío en segundo plano",
    }
    return await clientes_service.resend_onboarding_invite(
        cliente_id=str(cliente_id),
        empresa_id=str(current_user.empresa_id),
        background_tasks=background_tasks,
    )

