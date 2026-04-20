"""Portal autoservicio para cargadores (facturas y POD)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.api import deps
from app.db.supabase import SupabaseAsync
from app.schemas.bi import ProfitMarginAnalyticsOut
from app.schemas.portal_cliente import (
    PortalEsgResumenOut,
    PortalFacturaListItem,
    PortalPorteActivoListItem,
    PortalPorteListItem,
)
from app.schemas.user import UserOut
from app.services import esg_service
from app.services.esg_certificate_service import EsgCertificateService
from app.services.facturas_service import FacturasService
from app.services.portes_service import PortesService
from app.services.bi_service import BiService

router = APIRouter()


def _parse_fecha_entrega(raw: object) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        s = str(raw).strip()
        if not s:
            return None
        if "T" in s or "+" in s or s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return None


def _fecha_emision_date(raw: object) -> date:
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return date.today()


def _fecha_porte_date(raw: object) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


@router.get("/portes/activos", response_model=list[PortalPorteActivoListItem])
async def list_portes_activos(
    portal_user: UserOut = Depends(deps.require_portal_cliente),
    portes: PortesService = Depends(deps.get_portes_service),
) -> list[PortalPorteActivoListItem]:
    cid = portal_user.cliente_id
    assert cid is not None
    rows = await portes.list_portes_activos_cliente(
        empresa_id=portal_user.empresa_id,
        cliente_id=cid,
    )
    out: list[PortalPorteActivoListItem] = []
    for row in rows:
        out.append(
            PortalPorteActivoListItem(
                id=UUID(str(row["id"])),
                origen=str(row.get("origen") or ""),
                destino=str(row.get("destino") or ""),
                fecha=_fecha_porte_date(row.get("fecha")),
                estado=str(row.get("estado") or "pendiente"),
            )
        )
    return out


@router.get("/esg/export-csv")
async def portal_esg_export_csv(
    portal_user: UserOut = Depends(deps.require_portal_cliente),
    db: SupabaseAsync = Depends(deps.get_db),
) -> Response:
    """Histórico ESG YTD del cargador (mismas métricas CO₂ GLEC que certificado PDF)."""
    cid = portal_user.cliente_id
    assert cid is not None
    fname, csv_text = await esg_service.portal_cliente_esg_ytd_csv(
        db,
        empresa_id=str(portal_user.empresa_id),
        cliente_id=str(cid),
    )
    body = ("\ufeff" + csv_text).encode("utf-8")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/esg/resumen", response_model=PortalEsgResumenOut)
async def portal_esg_resumen(
    portal_user: UserOut = Depends(deps.require_portal_cliente),
    db: SupabaseAsync = Depends(deps.get_db),
) -> PortalEsgResumenOut:
    cid = portal_user.cliente_id
    assert cid is not None
    co2 = await esg_service.portal_cliente_esg_ytd_co2_ahorro_kg(
        db,
        empresa_id=str(portal_user.empresa_id),
        cliente_id=str(cid),
    )
    return PortalEsgResumenOut(co2_savings_ytd=co2)


@router.get("/analytics/profit-margin", response_model=ProfitMarginAnalyticsOut)
async def portal_analytics_profit_margin(
    portal_user: UserOut = Depends(deps.require_portal_cliente),
    db: SupabaseAsync = Depends(deps.get_db),
    range_from: Annotated[
        date | None,
        Query(alias="from", description="Inicio (YYYY-MM-DD), inclusive."),
    ] = None,
    range_to: Annotated[
        date | None,
        Query(alias="to", description="Fin (YYYY-MM-DD), inclusive."),
    ] = None,
    granularity: Annotated[Literal["month", "week"], Query()] = "month",
    vehiculo_id: Annotated[UUID | None, Query(description="Opcional: filtrar por vehículo asignado al porte.")] = None,
) -> ProfitMarginAnalyticsOut:
    """Misma agregación que ``GET /api/v1/analytics/profit-margin`` acotada al ``cliente_id`` del portal."""
    if range_from is not None and range_to is not None and range_from > range_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El parámetro from no puede ser posterior a to.",
        )
    cid = portal_user.cliente_id
    assert cid is not None
    svc = BiService(db)
    return await svc.profit_margin_analytics(
        empresa_id=str(portal_user.empresa_id),
        date_from=range_from,
        date_to=range_to,
        granularity=granularity,
        vehiculo_id=str(vehiculo_id) if vehiculo_id else None,
        cliente_id=str(cid),
    )


@router.get("/portes", response_model=list[PortalPorteListItem])
async def list_portes_entregados(
    portal_user: UserOut = Depends(deps.require_portal_cliente),
    portes: PortesService = Depends(deps.get_portes_service),
) -> list[PortalPorteListItem]:
    cid = portal_user.cliente_id
    assert cid is not None
    rows = await portes.list_portes_entregados_cliente(
        empresa_id=portal_user.empresa_id,
        cliente_id=cid,
    )
    out: list[PortalPorteListItem] = []
    for row in rows:
        fer = _parse_fecha_entrega(row.get("fecha_entrega_real"))
        out.append(
            PortalPorteListItem(
                id=UUID(str(row["id"])),
                origen=str(row.get("origen") or ""),
                destino=str(row.get("destino") or ""),
                fecha_entrega=fer,
            )
        )
    return out


@router.get("/facturas", response_model=list[PortalFacturaListItem])
async def list_facturas_cliente(
    portal_user: UserOut = Depends(deps.require_portal_cliente),
    facturas: FacturasService = Depends(deps.get_facturas_service),
) -> list[PortalFacturaListItem]:
    cid = portal_user.cliente_id
    assert cid is not None
    rows = await facturas.list_facturas_for_cliente(
        empresa_id=portal_user.empresa_id,
        cliente_id=cid,
    )
    out: list[PortalFacturaListItem] = []
    for row in rows:
        ec = str(row.get("estado_cobro") or "").strip().lower()
        pagada = ec in ("cobrada", "cobrado", "paid")
        try:
            total = float(row.get("total_factura") or 0)
        except (TypeError, ValueError):
            total = 0.0
        fid = row.get("id")
        xml_raw = str(row.get("xml_verifactu") or "").strip()
        out.append(
            PortalFacturaListItem(
                id=int(fid) if fid is not None else 0,
                numero_factura=str(row.get("numero_factura") or ""),
                fecha_emision=_fecha_emision_date(row.get("fecha_emision")),
                total_factura=total,
                estado_pago="Pagada" if pagada else "Pendiente",
                xml_verifactu_disponible=bool(xml_raw),
            )
        )
    return out


@router.get("/portes/{porte_id}/albaran-pdf")
async def download_albaran_pod_pdf(
    porte_id: UUID,
    portal_user: UserOut = Depends(deps.require_portal_cliente),
    portes: PortesService = Depends(deps.get_portes_service),
) -> Response:
    cid = portal_user.cliente_id
    assert cid is not None
    p = await portes.get_porte(empresa_id=str(portal_user.empresa_id), porte_id=str(porte_id))
    if p is None or str(p.cliente_id or "") != str(cid):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Porte no encontrado")
    try:
        pdf_bytes = await portes.get_albaran_entrega_pdf(
            empresa_id=portal_user.empresa_id,
            porte_id=str(porte_id),
        )
    except ValueError as e:
        msg = str(e).lower()
        if "no encontrado" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    safe = str(porte_id)[:12]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="albaran-{safe}.pdf"',
        },
    )


@router.get("/portes/{porte_id}/certificado-esg")
async def download_certificado_esg_porte(
    porte_id: UUID,
    official_audit: bool = Query(
        False,
        description="Solo plan Enterprise del transportista: solicita estado pending_external_audit.",
    ),
    portal_user: UserOut = Depends(deps.require_portal_cliente),
    portes: PortesService = Depends(deps.get_portes_service),
    esg: EsgCertificateService = Depends(deps.get_esg_certificate_service),
) -> Response:
    cid = portal_user.cliente_id
    assert cid is not None
    p = await portes.get_porte(empresa_id=str(portal_user.empresa_id), porte_id=str(porte_id))
    if p is None or str(p.cliente_id or "") != str(cid):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Porte no encontrado")
    uid = str(portal_user.usuario_id) if portal_user.usuario_id else portal_user.username
    pdf_bytes = await esg.generate_porte_certificate_pdf(
        empresa_id=str(portal_user.empresa_id),
        porte_id=str(porte_id),
        usuario_id=uid,
        official_audit=official_audit,
    )
    safe = str(porte_id)[:12]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="certificado-esg-{safe}.pdf"',
        },
    )


@router.get("/facturas/{factura_id}/pdf")
async def download_factura_pdf(
    factura_id: int,
    portal_user: UserOut = Depends(deps.require_portal_cliente),
    facturas: FacturasService = Depends(deps.get_facturas_service),
) -> Response:
    if factura_id < 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada")
    cid = portal_user.cliente_id
    assert cid is not None
    rows = await facturas.list_facturas_for_cliente(
        empresa_id=portal_user.empresa_id,
        cliente_id=cid,
    )
    allowed = {int(r["id"]) for r in rows if r.get("id") is not None}
    if factura_id not in allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada")
    try:
        pdf_bytes = await facturas.generate_factura_pdf_bytes(
            empresa_id=portal_user.empresa_id,
            factura_id=factura_id,
        )
    except ValueError as e:
        if "no encontrada" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="factura-{factura_id}.pdf"',
        },
    )


@router.get("/facturas/{factura_id}/xml")
async def download_factura_xml_verifactu(
    factura_id: int,
    portal_user: UserOut = Depends(deps.require_portal_cliente),
    facturas: FacturasService = Depends(deps.get_facturas_service),
) -> Response:
    if factura_id < 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada")
    cid = portal_user.cliente_id
    assert cid is not None
    xml = await facturas.get_xml_verifactu_for_cliente_factura(
        empresa_id=portal_user.empresa_id,
        cliente_id=cid,
        factura_id=factura_id,
    )
    if not xml:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="XML VeriFactu no disponible para esta factura",
        )
    return Response(
        content=xml.encode("utf-8"),
        media_type="application/xml; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="factura-{factura_id}-verifactu.xml"',
        },
    )
