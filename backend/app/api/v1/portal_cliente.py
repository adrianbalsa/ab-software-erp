"""Portal autoservicio para cargadores (facturas y POD)."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.api import deps
from app.schemas.portal_cliente import PortalFacturaListItem, PortalPorteListItem
from app.schemas.user import UserOut
from app.services.facturas_service import FacturasService
from app.services.portes_service import PortesService

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
        out.append(
            PortalFacturaListItem(
                id=int(fid) if fid is not None else 0,
                numero_factura=str(row.get("numero_factura") or ""),
                fecha_emision=_fecha_emision_date(row.get("fecha_emision")),
                total_factura=total,
                estado_pago="Pagada" if pagada else "Pendiente",
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
