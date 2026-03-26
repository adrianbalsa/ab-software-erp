"""
Exportación contable (diario ventas / compras) para gestoría (Sage, A3, Contaplus).
Importes con ``round_fiat`` (2 decimales HALF_EVEN) para cuadre al céntimo.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

import pandas as pd

from app.core.math_engine import round_fiat
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync

CuentaVentasDefault = "70000000"


def _cuenta_430_cliente(*, cliente_id: str, cuenta_contable: Any) -> str:
    raw = str(cuenta_contable or "").strip()
    if raw.isdigit() and len(raw) >= 8:
        return raw[:20]
    try:
        uid = UUID(str(cliente_id))
        suf = uid.int % 1_000_000
    except ValueError:
        h = hashlib.sha256(str(cliente_id).encode("utf-8")).hexdigest()
        suf = int(h[:12], 16) % 1_000_000
    return f"430{str(suf).zfill(5)}"


def _cuenta_400_proveedor(*, proveedor: str, gasto_id: str) -> str:
    h = hashlib.sha256(f"{proveedor}|{gasto_id}".encode("utf-8")).hexdigest()
    suf = int(h[:12], 16) % 1_000_000
    return f"400{str(suf).zfill(5)}"


def _cuenta_gasto_por_categoria(categoria: str | None) -> str:
    c = (categoria or "").strip().lower()
    if any(
        x in c
        for x in (
            "reparacion",
            "reparaciones",
            "taller",
            "mantenimiento",
            "mecanico",
            "mecánico",
            "neumatico",
            "neumático",
        )
    ):
        return "62200000"
    if any(
        x in c
        for x in (
            "suministro",
            "suministros",
            "combustible",
            "diesel",
            "gasolina",
            "gasoil",
            "adblue",
            "peaje",
            "peajes",
            "telefono",
            "teléfono",
            "luz",
            "agua",
        )
    ):
        return "62800000"
    return "62900000"


def _parse_date(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


class AccountingExportService:
    def __init__(self, db: SupabaseAsync) -> None:
        self._db = db

    async def _fetch_facturas_rango(
        self,
        *,
        empresa_id: str,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> list[dict[str, Any]]:
        eid = str(empresa_id).strip()
        res: Any = await self._db.execute(
            self._db.table("facturas")
            .select(
                "id, fecha_emision, numero_factura, num_factura, cliente, "
                "base_imponible, cuota_iva, total_factura"
            )
            .eq("empresa_id", eid)
            .gte("fecha_emision", fecha_inicio.isoformat())
            .lte("fecha_emision", fecha_fin.isoformat())
            .order("fecha_emision", desc=False)
        )
        return (res.data or []) if hasattr(res, "data") else []

    async def _fetch_clientes_map(
        self,
        *,
        empresa_id: str,
        cliente_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        if not cliente_ids:
            return {}
        eid = str(empresa_id).strip()
        res: Any = await self._db.execute(
            filter_not_deleted(
                self._db.table("clientes").select("*").eq("empresa_id", eid).in_("id", cliente_ids)
            )
        )
        rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            cid = str(r.get("id") or "")
            if cid:
                out[cid] = r
        return out

    async def _fetch_gastos_rango(
        self,
        *,
        empresa_id: str,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> list[dict[str, Any]]:
        eid = str(empresa_id).strip()
        q = filter_not_deleted(
            self._db.table("gastos")
            .select("id, fecha, proveedor, categoria, concepto, total_eur, total_chf, iva, moneda")
            .eq("empresa_id", eid)
            .gte("fecha", fecha_inicio.isoformat())
            .lte("fecha", fecha_fin.isoformat())
            .order("fecha", desc=False)
        )
        res: Any = await self._db.execute(q)
        return (res.data or []) if hasattr(res, "data") else []

    def generar_diario_ventas_df(
        self,
        *,
        facturas: list[dict[str, Any]],
        clientes: dict[str, dict[str, Any]],
    ) -> pd.DataFrame:
        rows_out: list[dict[str, Any]] = []
        for f in facturas:
            cid = str(f.get("cliente") or "").strip()
            cli = clientes.get(cid, {})
            if not cli and cid:
                try:
                    cli = clientes.get(str(UUID(cid)), {})
                except ValueError:
                    pass
            doc = str(f.get("numero_factura") or f.get("num_factura") or f.get("id") or "").strip()
            nombre = str(cli.get("nombre") or "").strip() or "—"
            cuenta = _cuenta_430_cliente(
                cliente_id=cid,
                cuenta_contable=cli.get("cuenta_contable") if cli else None,
            )
            fe = _parse_date(f.get("fecha_emision"))
            fecha_s = fe.isoformat() if fe else ""

            bi = f.get("base_imponible")
            if bi is None:
                tot = round_fiat(f.get("total_factura"))
                cuota_iv = round_fiat(f.get("cuota_iva"))
                base = round_fiat(tot - cuota_iv)
                cuota = cuota_iv
                total = tot
            else:
                base = round_fiat(bi)
                cuota = round_fiat(f.get("cuota_iva"))
                total = round_fiat(f.get("total_factura"))

            rows_out.append(
                {
                    "Fecha": fecha_s,
                    "Documento": doc,
                    "Cuenta Cliente": cuenta,
                    "Nombre Cliente": nombre,
                    "Base Imponible": float(base),
                    "Cuota IVA": float(cuota),
                    "Total": float(total),
                    "Cuenta Ventas": CuentaVentasDefault,
                }
            )
        return pd.DataFrame(rows_out)

    def generar_diario_compras_df(self, *, gastos: list[dict[str, Any]]) -> pd.DataFrame:
        rows_out: list[dict[str, Any]] = []
        for g in gastos:
            gid = str(g.get("id") or "")
            proveedor = str(g.get("proveedor") or "").strip()
            te = g.get("total_eur")
            if te is None:
                te = g.get("total_chf")
            total = round_fiat(te)
            iva_raw = g.get("iva")
            cuota = round_fiat(iva_raw) if iva_raw is not None else Decimal("0.00")
            base = round_fiat(total - cuota)
            if base < Decimal("0.00"):
                base = Decimal("0.00")

            fe = _parse_date(g.get("fecha"))
            fecha_s = fe.isoformat() if fe else ""
            doc = f"G-{gid[:8]}" if gid else ""
            cuenta_prov = _cuenta_400_proveedor(proveedor=proveedor or "—", gasto_id=gid or "0")
            cuenta_gas = _cuenta_gasto_por_categoria(str(g.get("categoria") or ""))

            rows_out.append(
                {
                    "Fecha": fecha_s,
                    "Documento": doc,
                    "Cuenta Proveedor": cuenta_prov,
                    "Nombre Proveedor": proveedor or "—",
                    "Base Imponible": float(base),
                    "Cuota IVA": float(cuota),
                    "Total": float(total),
                    "Cuenta Gasto": cuenta_gas,
                    "Categoria": str(g.get("categoria") or ""),
                }
            )
        return pd.DataFrame(rows_out)

    async def generar_diario_ventas(
        self,
        *,
        empresa_id: str,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> pd.DataFrame:
        facturas = await self._fetch_facturas_rango(
            empresa_id=empresa_id, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin
        )
        ids = sorted({str(f.get("cliente") or "").strip() for f in facturas if f.get("cliente")})
        clientes = await self._fetch_clientes_map(empresa_id=empresa_id, cliente_ids=ids)
        return self.generar_diario_ventas_df(facturas=facturas, clientes=clientes)

    async def generar_diario_compras(
        self,
        *,
        empresa_id: str,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> pd.DataFrame:
        gastos = await self._fetch_gastos_rango(
            empresa_id=empresa_id, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin
        )
        return self.generar_diario_compras_df(gastos=gastos)

    @staticmethod
    def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
        buf = io.StringIO()
        df.to_csv(buf, index=False, sep=";", decimal=",", encoding="utf-8-sig")
        return buf.getvalue().encode("utf-8-sig")

    @staticmethod
    def dataframes_to_excel_bytes(
        *,
        ventas: pd.DataFrame | None,
        compras: pd.DataFrame | None,
    ) -> bytes:
        bio = io.BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            if ventas is not None:
                ventas.to_excel(writer, sheet_name="Ventas", index=False)
            if compras is not None:
                compras.to_excel(writer, sheet_name="Compras", index=False)
        bio.seek(0)
        return bio.getvalue()

    @staticmethod
    def zip_csvs(files: list[tuple[str, bytes]]) -> bytes:
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, content in files:
                zf.writestr(name, content)
        bio.seek(0)
        return bio.getvalue()


TipoExport = Literal["ventas", "compras", "ambos"]
FormatoExport = Literal["csv", "excel"]


async def build_accounting_export(
    service: AccountingExportService,
    *,
    empresa_id: str,
    fecha_inicio: date,
    fecha_fin: date,
    tipo: TipoExport,
    formato: FormatoExport,
) -> tuple[bytes, str, str]:
    """
    Devuelve (cuerpo, media_type, filename).
    """
    df_v: pd.DataFrame | None = None
    df_c: pd.DataFrame | None = None
    if tipo in ("ventas", "ambos"):
        df_v = await service.generar_diario_ventas(
            empresa_id=empresa_id, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin
        )
    if tipo in ("compras", "ambos"):
        df_c = await service.generar_diario_compras(
            empresa_id=empresa_id, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin
        )

    tag = f"{fecha_inicio.isoformat()}_{fecha_fin.isoformat()}"

    if formato == "excel":
        body = AccountingExportService.dataframes_to_excel_bytes(
            ventas=df_v if tipo in ("ventas", "ambos") else None,
            compras=df_c if tipo in ("compras", "ambos") else None,
        )
        return (
            body,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"diario_contable_{tag}.xlsx",
        )

    if tipo == "ventas":
        df = df_v if df_v is not None else pd.DataFrame()
        body = AccountingExportService.dataframe_to_csv_bytes(df)
        return body, "text/csv; charset=utf-8", f"diario_ventas_{tag}.csv"
    if tipo == "compras":
        df = df_c if df_c is not None else pd.DataFrame()
        body = AccountingExportService.dataframe_to_csv_bytes(df)
        return body, "text/csv; charset=utf-8", f"diario_compras_{tag}.csv"

    v_b = AccountingExportService.dataframe_to_csv_bytes(df_v if df_v is not None else pd.DataFrame())
    c_b = AccountingExportService.dataframe_to_csv_bytes(df_c if df_c is not None else pd.DataFrame())
    body = AccountingExportService.zip_csvs(
        [
            (f"diario_ventas_{tag}.csv", v_b),
            (f"diario_compras_{tag}.csv", c_b),
        ]
    )
    return body, "application/zip", f"diario_contable_{tag}.zip"
