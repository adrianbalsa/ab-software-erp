from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status, Request
from supabase import AsyncClient

from app.api.auth_token import get_access_token
from app.core.supabase_client import get_supabase_async_client
from app.core.plans import (
    PLAN_ENTERPRISE,
    PLAN_PRO,
    PLAN_STARTER,
    fetch_empresa_plan,
    max_vehiculos,
    normalize_plan,
    plan_marketing_name,
)
from app.core.security import decode_access_token_payload
from app.db import supabase as supabase_db
from app.db.supabase import SupabaseAsync
from app.schemas.flota import FlotaVehiculoIn
from app.schemas.user import UserOut
from app.models.enums import UserRole, normalize_user_role
from app.services.auth_service import AuthService
from app.services.clientes_service import ClientesService
from app.services.refresh_token_service import RefreshTokenService
from app.services.eco_service import EcoService
from app.services.facturas_service import FacturasService
from app.services.finance_service import FinanceService
from app.services.flota_service import FlotaService
from app.services.gastos_service import GastosService
from app.services.esg_certificate_service import EsgCertificateService
from app.services.esg_service import EsgService
from app.services.maps_service import MapsService
from app.services.portes_service import PortesService
from app.services.presupuestos_service import PresupuestosService
from app.services.report_service import ReportService
from app.services.bank_service import BankService
from app.services.banking_service import BankingService
from app.services.banking_orchestrator import BankingOrchestratorService
from app.services.matching_service import MatchingService
from app.services.payment_service import PaymentService
from app.services.payments_gocardless import GoCardlessPaymentsService
from app.services.reconciliation_service import ReconciliationService
from app.services.accounting_export import AccountingExportService
from app.services.treasury_service import TreasuryService
from app.services.webhook_endpoints_service import WebhookEndpointsService
from app.services.webhooks_admin_service import WebhooksAdminService
from app.services.fleet_maintenance_service import FleetMaintenanceService
from app.services.stripe_service import assert_empresa_billing_active
from app.services.ai_service import LogisAdvisorService
from app.services.esg_audit_service import EsgAuditService
from app.services.esg_export_service import EsgExportService
from app.services.audit_logs_service import AuditLogsService
from app.services.bi_service import BiService
from app.services.geo_activity_service import GeoActivityService
from app.services.usage_quota_service import UsageQuotaService

_deps_log = logging.getLogger(__name__)

# Slugs de plan SaaS emitidos a veces en ``app_role`` / ``user_role`` del JWT; no deben
# forzar igualdad con ``profiles.role`` (el rol operativo viene del perfil en BD).
_JWT_APP_ROLE_SAAS_PLAN_SLUGS: frozenset[str] = frozenset(
    {
        "starter",
        "start",
        "basic",
        "compliance",
        "pro",
        "professional",
        "finance",
        "enterprise",
        "ent",
        "unlimited",
        "full-stack",
        "fullstack",
        "full_stack",
    },
)

_APP_METADATA_SUPPORTED_RBAC_ROLES: frozenset[str] = frozenset(
    {"owner", "admin", "driver", "traffic_manager", "cliente", "developer"}
)


def _extract_jwt_app_metadata_role(payload: dict[str, Any]) -> str | None:
    app_metadata = payload.get("app_metadata")
    if not isinstance(app_metadata, dict):
        return None
    role_raw = app_metadata.get("role")
    role = str(role_raw or "").strip().lower()
    if role in _APP_METADATA_SUPPORTED_RBAC_ROLES:
        return role
    return None


async def get_supabase(
    token: str = Depends(get_access_token),
) -> SupabaseAsync:
    """
    Cliente Supabase **siempre** inicializado con el JWT del request para aplicar RLS por usuario.
    Acepta ``Authorization: Bearer`` o cookie HttpOnly (nombre en ``ACCESS_TOKEN_COOKIE_NAME``).
    """
    return await supabase_db.get_supabase(jwt_token=token)


async def get_db(supabase: SupabaseAsync = Depends(get_supabase)) -> SupabaseAsync:
    return supabase


async def get_async_db(token: str = Depends(get_access_token)) -> AsyncClient:
    """
    AsyncClient nativo con JWT por request (RLS por usuario vía Authorization header).
    """
    return await get_supabase_async_client(access_token=token)


async def get_db_admin() -> SupabaseAsync:
    """
    Cliente con **service role** (bypass RLS) solo para rutas de autenticación que lo requieran
    explícitamente (``/auth/login``, ``/auth/refresh``). **No** usar en el resto de la API.
    """
    try:
        db = await supabase_db.get_supabase(
            jwt_token=None,
            allow_service_role_bypass=True,
            log_service_bypass_warning=False,
        )
        return db
    except Exception as exc:
        _deps_log.exception("get_db_admin: fallo al crear cliente Supabase (service role): %s", exc)
        print(f"GET_DB_ADMIN FAILED: {exc!r}", flush=True)
        raise


async def get_auth_service(db: SupabaseAsync = Depends(get_db)) -> AuthService:
    return AuthService(db)


async def get_auth_service_admin(db: SupabaseAsync = Depends(get_db_admin)) -> AuthService:
    """``AuthService`` con service role: solo ``/auth/login`` y ``/auth/refresh``."""
    try:
        svc = AuthService(db)
        _deps_log.debug("get_auth_service_admin: ok")
        return svc
    except Exception as exc:
        _deps_log.exception("get_auth_service_admin: %s", exc)
        print(f"GET_AUTH_SERVICE_ADMIN FAILED: {exc!r}", flush=True)
        raise


async def get_refresh_token_service(db: SupabaseAsync = Depends(get_db)) -> RefreshTokenService:
    return RefreshTokenService(db)


async def get_refresh_token_service_admin(db: SupabaseAsync = Depends(get_db_admin)) -> RefreshTokenService:
    """``RefreshTokenService`` con service role: solo ``/auth/login`` y ``/auth/refresh``."""
    try:
        return RefreshTokenService(db)
    except Exception as exc:
        _deps_log.exception("get_refresh_token_service_admin: %s", exc)
        print(f"GET_REFRESH_TOKEN_SERVICE_ADMIN FAILED: {exc!r}", flush=True)
        raise


async def get_maps_service(db: SupabaseAsync = Depends(get_db)) -> MapsService:
    return MapsService(db, UsageQuotaService(db))


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


async def get_facturas_service_async(db: AsyncClient = Depends(get_async_db)) -> FacturasService:
    return FacturasService(db)


async def get_esg_certificate_service(
    db: SupabaseAsync = Depends(get_db),
    portes: PortesService = Depends(get_portes_service),
    facturas: FacturasService = Depends(get_facturas_service),
) -> EsgCertificateService:
    return EsgCertificateService(db, portes, facturas)


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


async def get_esg_audit_service(db: SupabaseAsync = Depends(get_db)) -> EsgAuditService:
    return EsgAuditService(db)


async def get_esg_audit_service_admin(db: SupabaseAsync = Depends(get_db_admin)) -> EsgAuditService:
    """Service role: transiciones de certificado / flujos cross-tenant controlados en ruta."""
    return EsgAuditService(db)


async def get_esg_export_service_admin(db: SupabaseAsync = Depends(get_db_admin)) -> EsgExportService:
    """Service role: export auditor-ready (sin PII) para administración."""
    return EsgExportService(db)


async def get_esg_export_service(db: SupabaseAsync = Depends(get_db)) -> EsgExportService:
    """RLS tenant: mismas filas agregadas ISO 14083 que el export admin (sin PII en líneas)."""
    return EsgExportService(db)


async def get_audit_logs_service(db: SupabaseAsync = Depends(get_db)) -> AuditLogsService:
    return AuditLogsService(db)


async def get_bi_service(db: SupabaseAsync = Depends(get_db)) -> BiService:
    return BiService(db)


async def get_geo_activity_service(db: SupabaseAsync = Depends(get_db)) -> GeoActivityService:
    return GeoActivityService(db)


async def get_usage_quota_service(db: SupabaseAsync = Depends(get_db)) -> UsageQuotaService:
    return UsageQuotaService(db)


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


async def get_banking_service(db: SupabaseAsync = Depends(get_db)) -> BankingService:
    return BankingService(db)


async def get_matching_service(db: SupabaseAsync = Depends(get_db)) -> MatchingService:
    return MatchingService(db)


async def get_reconciliation_service(
    db: SupabaseAsync = Depends(get_db),
    advisor: LogisAdvisorService = Depends(get_logis_advisor_service),
) -> ReconciliationService:
    return ReconciliationService(db, logis_advisor=advisor)


async def get_banking_orchestrator(
    matching: MatchingService = Depends(get_matching_service),
    recon: ReconciliationService = Depends(get_reconciliation_service),
) -> BankingOrchestratorService:
    return BankingOrchestratorService(matching, recon)


async def get_payment_service(db: SupabaseAsync = Depends(get_db)) -> PaymentService:
    return PaymentService(db)


async def get_gocardless_payments_service() -> GoCardlessPaymentsService:
    return GoCardlessPaymentsService()


async def get_treasury_service(db: SupabaseAsync = Depends(get_db)) -> TreasuryService:
    return TreasuryService(db)


async def get_webhooks_admin_service(db: SupabaseAsync = Depends(get_db)) -> WebhooksAdminService:
    return WebhooksAdminService(db)


async def get_webhook_endpoints_service(db: SupabaseAsync = Depends(get_db)) -> WebhookEndpointsService:
    return WebhookEndpointsService(db)


async def get_fleet_maintenance_service(db: SupabaseAsync = Depends(get_db)) -> FleetMaintenanceService:
    return FleetMaintenanceService(db)


async def get_accounting_export_service(db: SupabaseAsync = Depends(get_db)) -> AccountingExportService:
    return AccountingExportService(db)


async def get_current_user(
    token: str = Depends(get_access_token),
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

    jwt_cliente = payload.get("cliente_id")
    if jwt_cliente is not None and str(jwt_cliente).strip():
        try:
            jc = UUID(str(jwt_cliente).strip())
        except ValueError:
            raise credentials_exc
        if user_out.cliente_id is None or user_out.cliente_id != jc:
            raise credentials_exc

    jwt_role = payload.get("role")
    if jwt_role is not None and str(jwt_role).strip():
        normalized_jwt_role = str(jwt_role).strip().lower()
        # Supabase access tokens typically carry role=authenticated.
        if normalized_jwt_role not in {"authenticated", "service_role"}:
            raise credentials_exc

    role_claim_for_match = payload.get("app_role") or payload.get("user_role")
    if role_claim_for_match is not None and str(role_claim_for_match).strip():
        raw_claim = str(role_claim_for_match).strip().lower()
        if raw_claim not in _JWT_APP_ROLE_SAAS_PLAN_SLUGS:
            try:
                expected_role = normalize_user_role(str(role_claim_for_match))
            except Exception:
                raise credentials_exc
            if user_out.role != expected_role:
                raise credentials_exc

    jwt_app_role = _extract_jwt_app_metadata_role(payload)
    if jwt_app_role:
        user_out.rbac_role = jwt_app_role
        try:
            user_out.role = normalize_user_role(jwt_app_role, legacy_role=user_out.rol)
        except Exception:
            user_out.role = normalize_user_role(user_out.role, legacy_role=user_out.rol)

    await auth_service.ensure_empresa_context(empresa_id=user_out.empresa_id)
    await auth_service.ensure_rbac_context(user=user_out)
    return user_out


def _normalize_role(role: str | Enum) -> UserRole:
    if isinstance(role, UserRole):
        return role

    candidate = role.value if isinstance(role, Enum) else role
    if not isinstance(candidate, str):
        raise TypeError("Role must be a string or Enum value")

    normalized = candidate.strip()
    if not normalized:
        raise ValueError("Role cannot be empty")

    # Accept enum member names (e.g. "ADMIN") and values (e.g. "admin").
    upper_name = normalized.upper()
    if upper_name in UserRole.__members__:
        return UserRole[upper_name]

    return normalize_user_role(normalized.lower())


class RoleChecker:
    """
    Único checker RBAC de API: fuente de verdad = current_user.role.
    """

    def __init__(self, allowed_roles: list[str | UserRole]):
        self.allowed_roles = frozenset(
            r if isinstance(r, UserRole) else _normalize_role(r) for r in allowed_roles
        )

    async def __call__(self, current_user: UserOut = Depends(get_current_user)) -> UserOut:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough privileges",
            )
        return current_user


async def _enforce_role(current_user: UserOut, allowed_roles: frozenset[UserRole]) -> UserOut:
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough privileges",
        )
    return current_user


def require_role(*allowed_roles: str):
    """
    Dependencia RBAC operativa (profiles.role). El JWT solo complementa UX;
    la fuente de verdad es el perfil recargado vía ``get_current_user``.
    """
    checker = RoleChecker(list(allowed_roles))

    async def _dep(current_user: UserOut = Depends(get_current_user)) -> UserOut:
        return await checker(current_user)

    return _dep


def require_write_role(*allowed_roles: str):
    """
    Igual que ``require_role`` pero reafirma el contexto de tenant antes de mutar datos.
    """
    normalized_allowed = frozenset(_normalize_role(role) for role in allowed_roles)

    async def _dep(current_user: UserOut = Depends(bind_write_context)) -> UserOut:
        return await _enforce_role(current_user, normalized_allowed)

    return _dep


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
    await auth_service.ensure_rbac_context(user=current_user)
    return current_user


async def assert_resource_belongs_to_current_empresa(
    *,
    db: SupabaseAsync,
    current_user: UserOut,
    table_name: str,
    resource_id: str,
    id_column: str = "id",
    empresa_column: str = "empresa_id",
) -> None:
    """
    Verifica ownership multi-tenant de un recurso por ``empresa_id``.
    Devuelve 404 para no filtrar existencia entre tenants.
    """
    rid = str(resource_id or "").strip()
    if not rid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identificador de recurso inválido.",
        )

    q = (
        db.table(table_name)
        .select(f"{id_column},{empresa_column}")
        .eq(id_column, rid)
        .eq(empresa_column, str(current_user.empresa_id))
        .limit(1)
    )
    res: Any = await db.execute(q)
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurso no encontrado",
        )


def require_tenant_resource(
    *,
    table_name: str,
    path_param: str,
    id_column: str = "id",
    empresa_column: str = "empresa_id",
) -> Callable[..., Any]:
    """
    Dependencia inyectable para validar que un ``path_param`` pertenece al tenant actual.
    """

    async def _dep(
        request: Request,
        current_user: UserOut = Depends(get_current_user),
        db: SupabaseAsync = Depends(get_db),
    ) -> None:
        raw_id = request.path_params.get(path_param)
        await assert_resource_belongs_to_current_empresa(
            db=db,
            current_user=current_user,
            table_name=table_name,
            resource_id=str(raw_id or ""),
            id_column=id_column,
            empresa_column=empresa_column,
        )

    return _dep


async def require_admin_user(current_user: UserOut = Depends(get_current_user)) -> UserOut:
    if current_user.role not in {UserRole.ADMIN, UserRole.SUPERADMIN, UserRole.DEVELOPER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: requiere rol admin",
        )
    return current_user


async def require_admin_write_user(
    current_user: UserOut = Depends(bind_write_context),
) -> UserOut:
    """Admin con contexto de tenant re-afirmado (POST/PATCH/DELETE)."""
    if current_user.role not in {UserRole.ADMIN, UserRole.SUPERADMIN, UserRole.DEVELOPER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: requiere rol admin",
        )
    return current_user


async def require_portal_cliente(
    _jwt_ok: UserOut = Depends(RoleChecker(["cliente"])),
    current_user: UserOut = Depends(get_current_user),
) -> UserOut:
    """
    Usuario portal: JWT con rol cliente + perfil ``profiles.role=cliente`` y ``cliente_id`` obligatorio.
    """
    if current_user.role != UserRole.CLIENTE or current_user.cliente_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere cuenta de portal cliente (perfil incompleto).",
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
    if current_user.role not in {UserRole.ADMIN, UserRole.SUPERADMIN, UserRole.DEVELOPER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: requiere rol admin",
        )
    await auth_service.ensure_empresa_context(empresa_id=current_user.empresa_id)
    await auth_service.ensure_rbac_context(user=current_user)
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
                        f"Has alcanzado el límite de 5 camiones de tu plan {plan_marketing_name(pn)}. "
                        "Mejora a Finance para gestionar hasta 25 y activar el cálculo de EBITDA real."
                    ),
                )
            if pn == PLAN_PRO:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Has alcanzado el límite de 25 vehículos de tu plan {plan_marketing_name(pn)}. "
                        f"Pasa a {plan_marketing_name(PLAN_ENTERPRISE)} para flota ilimitada y el módulo ESG completo."
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
                    f"El cálculo de huella de carbono es exclusivo para el plan {plan_marketing_name(PLAN_ENTERPRISE)}. "
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
                    f"La exportación fiscal para inspección AEAT está disponible en planes "
                    f"{plan_marketing_name(PLAN_PRO)} y {plan_marketing_name(PLAN_ENTERPRISE)}."
                ),
            )

        return _exportacion_aeat

    raise ValueError(f"check_quota_limit: recurso desconocido {resource!r}")

