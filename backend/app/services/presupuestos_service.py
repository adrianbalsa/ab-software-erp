from __future__ import annotations

from app.schemas.presupuesto import (
    PresupuestoCalculoIn,
    PresupuestoCalculoOut,
    PresupuestoLineaOut,
)
from app.services.verifactu_service import VerifactuService


class PresupuestosService:
    """
    Pure calculation service (no DB).
    Mirrors Streamlit logic from `views/presupuestos_view.py`.
    """

    async def calcular(self, *, payload: PresupuestoCalculoIn) -> PresupuestoCalculoOut:
        # Subtotales base
        subtotal_obra = float(payload.metros_obra) * float(payload.precio_m2)

        total_horas_humanas = int(payload.num_trabajadores) * float(payload.horas_por_trab)
        subtotal_mo = float(total_horas_humanas) * float(payload.coste_hora)

        subtotal_materiales = float(
            sum(float(l.cantidad) * float(l.precio) for l in (payload.materiales or []))
        )

        # Aplicar margen
        factor_margen = 1.0 + (float(payload.margen_pct) / 100.0)
        subtotal_obra_final = subtotal_obra * factor_margen
        subtotal_mo_final = subtotal_mo * factor_margen
        subtotal_materiales_final = subtotal_materiales * factor_margen

        subtotal_final = subtotal_obra_final + subtotal_mo_final + subtotal_materiales_final
        cuota_iva = subtotal_final * (float(payload.iva_pct) / 100.0)
        total_final = subtotal_final + cuota_iva

        # Items (detalle) – como en la vista: precios ya con margen
        items: list[PresupuestoLineaOut] = []
        if subtotal_obra > 0:
            items.append(
                PresupuestoLineaOut(
                    concepto=f"Ejecución de Obra Civil ({payload.metros_obra} m2)",
                    cantidad=float(payload.metros_obra),
                    precio_unitario=float(payload.precio_m2) * factor_margen,
                    total=float(subtotal_obra_final),
                )
            )
        if subtotal_mo > 0:
            items.append(
                PresupuestoLineaOut(
                    concepto=(
                        "Mano de Obra Especializada "
                        f"({payload.num_trabajadores} operarios x {payload.horas_por_trab}h)"
                    ),
                    cantidad=float(total_horas_humanas),
                    precio_unitario=float(payload.coste_hora) * factor_margen,
                    total=float(subtotal_mo_final),
                )
            )

        for mat in payload.materiales or []:
            if (mat.descripcion or "").strip() and float(mat.precio) > 0 and float(mat.cantidad) > 0:
                items.append(
                    PresupuestoLineaOut(
                        concepto=str(mat.descripcion),
                        cantidad=float(mat.cantidad),
                        precio_unitario=float(mat.precio) * factor_margen,
                        total=float(mat.cantidad) * float(mat.precio) * factor_margen,
                    )
                )

        # Encadenado hash (VeriFactu helpers)
        hash_documento: str | None = None
        if payload.verifactu is not None:
            v = payload.verifactu
            hash_documento = VerifactuService.generar_hash_factura(
                nif_empresa=v.nif_empresa,
                nif_cliente=v.nif_cliente,
                num_factura=v.num_documento,
                fecha=v.fecha,
                total=total_final,
                hash_anterior=v.hash_anterior,
            )

        return PresupuestoCalculoOut(
            subtotal_obra=float(subtotal_obra),
            subtotal_mo=float(subtotal_mo),
            subtotal_materiales=float(subtotal_materiales),
            subtotal_obra_final=float(subtotal_obra_final),
            subtotal_mo_final=float(subtotal_mo_final),
            subtotal_materiales_final=float(subtotal_materiales_final),
            subtotal_final=float(subtotal_final),
            cuota_iva=float(cuota_iva),
            total_final=float(total_final),
            items=items,
            moneda=payload.moneda,
            hash_documento=hash_documento,
        )
