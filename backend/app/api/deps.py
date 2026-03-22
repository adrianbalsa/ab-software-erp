from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.plans import (
    PLAN_ENTERPRISE,
    PLAN_PRO,
    PLAN_STARTER,
    fetch_empresa_plan,
    max_vehiculos,
    normalize_plan,
)
from app.core.security import decode_access_token_payload
from app.db import supabase as supabase_db
from app.db.supabase import SupabaseAsync
from app.schemas.flota import FlotaVehiculoIn
from app.schemas.user import UserOut
from app.services.auth_service import AuthService
from app.services.clientes_service import ClientesService
from app.services.refresh_token_service import RefreshTokenService
from app.services.eco_service import EcoService
from app.services.facturas_service import FacturasService
from app.services.finance_service import FinanceService
from app.services.flota_service import FlotaService
from app.services.gastos_service import GastosService
from app.services.esg_service import EsgService
from app.services.maps_service import MapsService
from app.services.portes_service import PortesService
from app.services.presupuestos_service import PresupuestosService
from app.services.report_service import ReportService
from app.services.bank_service import BankService
from app.services.stripe_service import assert_empresa_billing_active
from app.services.ai_service import LogisAdvisorService


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Mismo esquema OAuth2 pero sin 401 si falta Authorization (login, health, docs).
reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_supabase(token: str | None = Depends(reusable_oauth2)) -> SupabaseAsync:
    """
    Cliente Supabase con **identidad del usuario** en la cabecera (JWT + anon key → RLS).

    Sin ``Authorization: Bearer``, cliente **anon** sin bypass (ver ``app.db.supabase``).
    """
    return await supabase_db.get_supabase(jwt_token=token)


async def get_db(supabase: SupabaseAsync = Depends(get_supabase)) -> SupabaseAsync:
    return supabase


async def get_db_admin() -> SupabaseAsync:
    """
    Cliente con **service role** (bypass RLS) solo para rutas de autenticación que lo requieran
    explícitamente (``/auth/login``, ``/auth/refresh``). **No** usar en el resto de la API.
    """
    return await supabase_db.get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )


async def get_auth_service(db: SupabaseAsync = Depends(get_db)) -> AuthService:
    return AuthService(db)


async def get_auth_service_admin(db: SupabaseAsync = Depends(get_db_admin)) -> AuthService:
    """``AuthService`` con service role: solo ``/auth/login`` y ``/auth/refresh``."""
    return AuthService(db)


async def get_refresh_token_service(db: SupabaseAsync = Depends(get_db)) -> RefreshTokenService:
    return RefreshTokenService(db)


async def get_refresh_token_service_admin(db: SupabaseAsync = Depends(get_db_admin)) -> RefreshTokenService:
    """``RefreshTokenService`` con service role: solo ``/auth/login`` y ``/auth/refresh``."""
    return RefreshTokenService(db)


async def get_maps_service(db: SupabaseAsync = Depends(get_db)) -> MapsService:
    return MapsService(db)


async def get_esg_service(
    db: SupabaseAsync = Depends(get_db),
    maps: MapsService = Depends(get_maps_service),
) -> EsgService:
    return EsgService(db, maps)


async def get_portes_service(
    db: SupabaseAsync = Depends(get_db),
    maps: MapsService = Depends(get_maps_service),
) -> PortesService:
    return PortesService(db, maps)


async def get_clientes_service(db: SupabaseAsync = Depends(get_db)) -> ClientesService:
    return ClientesService(db)


async def get_facturas_service(db: SupabaseAsync = Depends(get_db)) -> FacturasService:
    return FacturasService(db)

async def get_presupuestos_service() -> PresupuestosService:
    # Pure service (no DB)
    return PresupuestosService()


async def get_gastos_service(db: SupabaseAsync = Depends(get_db)) -> GastosService:
    return GastosService(db)

async def get_eco_service(db: SupabaseAsync = Depends(get_db)) -> EcoService:
    return EcoService(db)

async def get_flota_service(db: SupabaseAsync = Depends(get_db)) -> FlotaService:
    return FlotaService(db)


async def get_finance_service(db: SupabaseAsync = Depends(get_db)) -> FinanceService:
    return FinanceService(db)


async def get_logis_advisor_service(
    finance: FinanceService = Depends(get_finance_service),
    facturas: FacturasService = Depends(get_facturas_service),
    flota: FlotaService = Depends(get_flota_service),
    maps: MapsService = Depends(get_maps_service),
    esg: EsgService = Depends(get_esg_service),
) -> LogisAdvisorService:
    return LogisAdvisorService(finance, facturas, flota, maps, esg)


async def get_report_service(db: SupabaseAsync = Depends(get_db)) -> ReportService:
    return ReportService(db)


async def get_bank_service(db: SupabaseAsync = Depends(get_db)) -> BankService:
    return BankService(db)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserOut:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload: dict[str, Any] = decode_access_token_payload(token)
    except ValueError:
        raise credentials_exc

    sub_raw = payload.get("sub")
    if sub_raw is None or not str(sub_raw).strip():
        raise credentials_exc
    subject = str(sub_raw).strip()

    user_out = await auth_service.get_profile_by_subject(subject=subject)
    if user_out is None:
        raise credentials_exc

    jwt_empresa = payload.get("empresa_id")
    if jwt_empresa is not None and str(jwt_empresa).strip():
        try:
            expected = UUID(str(jwt_empresa).strip())
        except ValueError:
            raise credentials_exc
        if user_out.empresa_id != expected:
            raise credentials_exc

    await auth_service.ensure_empresa_context(empresa_id=user_out.empresa_id)
    return user_out


async def get_current_active_user(
    current_user: UserOut = Depends(get_current_user),
    db: SupabaseAsync = Depends(get_db),
) -> UserOut:
    """
    Igual que ``get_current_user`` y además valida que la empresa esté operativa
    (no archivada; suscripción Stripe activa si aplica).
    """
    await assert_empresa_billing_active(db, empresa_id=str(current_user.empresa_id))
    return current_user


async def get_usuario_db_id(
    current_user: UserOut = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> str | None:
    """
    ``usuarios.id`` (UUID) alineado con ``refresh_tokens.user_id``.
    Necesario para gestión de sesiones; None si el login no tiene fila ``usuarios`` con id.
    """
    u = await auth_service.get_user(username=current_user.username)
    if u is None or not u.id:
        return None
    return str(u.id).strip()


async def bind_write_context(
    current_user: UserOut = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserOut:
    """
    Segunda llamada a ``set_empresa_context`` inmediatamente antes de mutar datos
    (defensa en profundidad frente a fugas de contexto entre corrutinas / pool HTTP).
    """
    await auth_service.ensure_empresa_context(empresa_id=current_user.empresa_id)
    return current_user


async def require_admin_user(current_user: UserOut = Depends(get_current_user)) -> UserOut:
    if current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: requiere rol admin",
        )
    return current_user


async def require_admin_write_user(
    current_user: UserOut = Depends(bind_write_context),
) -> UserOut:
    """Admin con contexto de tenant re-afirmado (POST/PATCH/DELETE)."""
    if current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: requiere rol admin",
        )
    return current_user


async def require_admin_active_write_user(
    current_user: UserOut = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserOut:
    """
    Empresa activa (facturación), rol admin y ``ensure_empresa_context`` antes de mutar datos
    (p. ej. Open Banking).
    """
    if current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: requiere rol admin",
        )
    await auth_service.ensure_empresa_context(empresa_id=current_user.empresa_id)
    return current_user


def check_quota_limit(resource: str):
    """
    Factoría de dependencias FastAPI para cuotas y flags por plan SaaS.

    - ``vehiculos``: valida el inventario enviado (POST sustituye la flota activa).
    - ``esg``: solo ``enterprise`` (Sostenibilidad / ESG).
    - ``exportacion_aeat``: exportación fiscal inspección — solo ``pro`` y ``enterprise``.
    """

    if resource == "vehiculos":

        async def _vehiculos(
            vehiculos_in: list[FlotaVehiculoIn],
            current_user: UserOut = Depends(bind_write_context),
            db: SupabaseAsync = Depends(get_db),
        ) -> None:
            plan = await fetch_empresa_plan(db, empresa_id=str(current_user.empresa_id))
            cap = max_vehiculos(plan)
            if cap is None:
                return
            if len(vehiculos_in) <= cap:
                return
            pn = normalize_plan(plan)
            if pn == PLAN_STARTER:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Has alcanzado el límite de 5 camiones de tu plan Starter. "
                        "Mejora a PRO para gestionar hasta 25 y activar el cálculo de EBITDA real."
                    ),
                )
            if pn == PLAN_PRO:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Has alcanzado el límite de 25 vehículos de tu plan PRO. "
                        "Pasa a Enterprise para flota ilimitada y el módulo ESG completo."
                    ),
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Límite de vehículos excedido para tu plan actual.",
            )

        return _vehiculos

    if resource == "esg":

        async def _esg(
            current_user: UserOut = Depends(get_current_user),
            db: SupabaseAsync = Depends(get_db),
        ) -> None:
            plan = await fetch_empresa_plan(db, empresa_id=str(current_user.empresa_id))
            if normalize_plan(plan) == PLAN_ENTERPRISE:
                return
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "El cálculo de huella de carbono es exclusivo para el plan Enterprise. "
                    "Ayuda a tus clientes a cumplir sus objetivos de sostenibilidad haciendo el upgrade."
                ),
            )

        return _esg

    if resource == "exportacion_aeat":

        async def _exportacion_aeat(
            current_user: UserOut = Depends(get_current_user),
            db: SupabaseAsync = Depends(get_db),
        ) -> None:
            plan = await fetch_empresa_plan(db, empresa_id=str(current_user.empresa_id))
            pn = normalize_plan(plan)
            if pn in (PLAN_PRO, PLAN_ENTERPRISE):
                return
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "La exportación fiscal para inspección AEAT está disponible en planes PRO y Enterprise."
                ),
            )

        return _exportacion_aeat

    raise ValueError(f"check_quota_limit: recurso desconocido {resource!r}")

