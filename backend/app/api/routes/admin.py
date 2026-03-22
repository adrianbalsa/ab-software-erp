from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.api import deps
from app.db.supabase import SupabaseAsync
from app.schemas.admin_panel import (
    AuditoriaAdminRow,
    MetricasSaaSFacturacionOut,
    UsuarioAdminOut,
    UsuarioAdminPatch,
)
from app.schemas.empresa import EmpresaCreate, EmpresaOut, EmpresaUpdate
from app.schemas.user import UserOut
from app.services.admin_service import AdminService


router = APIRouter()


async def _get_admin_service(db: SupabaseAsync = Depends(deps.get_db)) -> AdminService:
    return AdminService(db)


@router.get("/empresas", response_model=list[EmpresaOut])
async def list_empresas(
    admin_user: UserOut = Depends(deps.require_admin_user),
    service: AdminService = Depends(_get_admin_service),
) -> list[EmpresaOut]:
    _ = admin_user
    return await service.list_empresas()


@router.post("/empresas", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED)
async def create_empresa(
    empresa_in: EmpresaCreate,
    admin_user: UserOut = Depends(deps.require_admin_write_user),
    service: AdminService = Depends(_get_admin_service),
) -> EmpresaOut:
    _ = admin_user
    try:
        return await service.create_empresa(empresa_in=empresa_in)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/empresas/{empresa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_empresa(
    empresa_id: str,
    admin_user: UserOut = Depends(deps.require_admin_write_user),
    service: AdminService = Depends(_get_admin_service),
) -> Response:
    """Archiva la empresa (`deleted_at`); no borra físicamente."""
    _ = admin_user
    try:
        await service.soft_delete_empresa(empresa_id=empresa_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/empresas/{empresa_id}", response_model=EmpresaOut)
async def update_empresa(
    empresa_id: str,
    patch: EmpresaUpdate,
    admin_user: UserOut = Depends(deps.require_admin_write_user),
    service: AdminService = Depends(_get_admin_service),
) -> EmpresaOut:
    _ = admin_user
    try:
        return await service.update_empresa(empresa_id=empresa_id, patch=patch)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/usuarios", response_model=list[UsuarioAdminOut])
async def list_usuarios(
    admin_user: UserOut = Depends(deps.require_admin_user),
    service: AdminService = Depends(_get_admin_service),
) -> list[UsuarioAdminOut]:
    _ = admin_user
    return await service.list_usuarios()


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioAdminOut)
async def update_usuario(
    usuario_id: str,
    patch: UsuarioAdminPatch,
    admin_user: UserOut = Depends(deps.require_admin_write_user),
    service: AdminService = Depends(_get_admin_service),
) -> UsuarioAdminOut:
    _ = admin_user
    try:
        return await service.update_usuario(usuario_id=usuario_id, patch=patch)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/auditoria", response_model=list[AuditoriaAdminRow])
async def list_auditoria(
    limit: int = Query(100, ge=10, le=500),
    admin_user: UserOut = Depends(deps.require_admin_user),
    service: AdminService = Depends(_get_admin_service),
) -> list[AuditoriaAdminRow]:
    _ = admin_user
    return await service.list_auditoria(limit=limit)


@router.get("/metricas/facturacion", response_model=MetricasSaaSFacturacionOut)
async def metricas_saas_facturacion(
    admin_user: UserOut = Depends(deps.require_admin_user),
    service: AdminService = Depends(_get_admin_service),
) -> MetricasSaaSFacturacionOut:
    _ = admin_user
    try:
        return await service.metricas_saas_facturacion()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

