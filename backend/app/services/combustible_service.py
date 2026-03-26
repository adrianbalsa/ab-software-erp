"""
Importación CSV de combustible (Solred / StarRessa / Edenred): gastos, ESG (``esg_auditoria`` + trigger CO2), odómetro.
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import pandas as pd

from app.db.soft_delete import filter_not_deleted
from app.db.supabase import SupabaseAsync
from app.schemas.gasto import GastoCreate
from app.services.gastos_service import GastosService

_log = logging.getLogger(__name__)


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _norm_matricula_key(raw: Any) -> str:
    s = _strip_accents(str(raw or "")).strip().upper()
    return "".join(c for c in s if c.isalnum())


def _norm_col_key(raw: Any) -> str:
    s = _strip_accents(str(raw or "")).strip().upper()
    return "".join(c for c in s if c.isalnum())


def _parse_fecha(raw: Any) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    s = str(raw).strip()
    if not s:
        return None
    if len(s) >= 10:
        s = s[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", s)
        if not m:
            return None
        dd = int(m.group(1))
        mm = int(m.group(2))
        yy = int(m.group(3))
        if yy < 100:
            yy += 2000
        return date(yy, mm, dd)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        v = pd.to_numeric(value, errors="coerce")
    except Exception:
        return None
    if pd.isna(v):  # type: ignore[attr-defined]
        return None
    return float(v)


def _detect_columns(df: pd.DataFrame) -> dict[str, str | None]:
    col_by_norm = {_norm_col_key(c): c for c in df.columns}

    fecha_candidates = [c for k, c in col_by_norm.items() if k == "FECHA"]
    if not fecha_candidates:
        fecha_candidates = [c for k, c in col_by_norm.items() if "FECHA" in k]
    fecha_col = fecha_candidates[0] if fecha_candidates else None

    mat_candidates = [
        c
        for k, c in col_by_norm.items()
        if k.startswith("MATRIC") or k == "MATRICULA" or "MATRIC" in k
    ]
    matricula_col = mat_candidates[0] if mat_candidates else None

    litros_candidates = [c for k, c in col_by_norm.items() if k.startswith("LITRO") or "LITRO" in k]
    litros_col = litros_candidates[0] if litros_candidates else None

    importe_col = None
    for k, c in col_by_norm.items():
        if "IMPORTE" in k and ("TOTAL" in k):
            importe_col = c
            break
    if importe_col is None:
        importe_candidates = [c for k, c in col_by_norm.items() if "IMPORTE" in k]
        importe_col = importe_candidates[0] if importe_candidates else None

    proveedor_col = None
    for k, c in col_by_norm.items():
        if k == "PROVEEDOR" or k.startswith("PROVEEDOR"):
            proveedor_col = c
            break

    estacion_candidates = [c for k, c in col_by_norm.items() if "ESTACION" in k]
    estacion_col = estacion_candidates[0] if estacion_candidates else None

    km_col = None
    for k, c in col_by_norm.items():
        if k in ("KILOMETROS", "KILOMETRO", "KM", "ODOMETRO", "ODOMETROACTUAL"):
            km_col = c
            break
    if km_col is None:
        for k, c in col_by_norm.items():
            if "KILOM" in k or (k.endswith("KM") and len(k) <= 12):
                km_col = c
                break

    missing: list[str] = []
    if not fecha_col:
        missing.append("Fecha")
    if not matricula_col:
        missing.append("Matricula")
    if not litros_col:
        missing.append("Litros")
    if not importe_col:
        missing.append("Importe_Total")
    if missing:
        raise ValueError(
            "Formato de archivo no reconocido. Faltan columnas: " + ", ".join(missing)
        )

    return {
        "fecha": str(fecha_col),
        "matricula": str(matricula_col),
        "litros": str(litros_col),
        "importe_total": str(importe_col),
        "proveedor": str(proveedor_col) if proveedor_col else None,
        "estacion": str(estacion_col) if estacion_col else None,
        "kilometros": str(km_col) if km_col else None,
    }


def _read_dataframe(raw: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(io.BytesIO(raw))
    decoded = raw.decode("utf-8", errors="ignore")
    try:
        return pd.read_csv(io.StringIO(decoded), sep=";")
    except Exception:
        try:
            return pd.read_csv(io.StringIO(decoded), sep=",")
        except Exception:
            return pd.read_csv(io.StringIO(decoded), sep=None, engine="python")


@dataclass(frozen=True, slots=True)
class FuelImportResult:
    total_filas_leidas: int
    filas_importadas_ok: int
    total_litros: float
    total_euros: float
    total_co2_kg: float
    errores: list[str]


async def importar_combustible_csv(
    *,
    raw: bytes,
    filename: str,
    empresa_id: str,
    username_empleado: str,
    db: SupabaseAsync,
    gastos_service: GastosService,
) -> FuelImportResult:
    """
    Procesa CSV/Excel de combustible: ``gastos``, ``gastos_vehiculo``, ``esg_auditoria`` (CO2 vía trigger),
    y opcionalmente actualiza ``flota.odometro_actual`` si la columna de kilómetros supera el valor actual.
    """
    if not filename:
        raise ValueError("Archivo sin nombre")

    try:
        df = _read_dataframe(raw, filename)
    except Exception as e:
        raise ValueError(f"No se pudo parsear el archivo: {e}") from e

    if df is None or df.empty:
        raise ValueError("El archivo no contiene filas")

    col = _detect_columns(df)
    df = df.copy()
    df["_mat_key"] = df[col["matricula"]].apply(_norm_matricula_key)
    df["_mat_display"] = df[col["matricula"]].apply(lambda x: str(x).strip() if x is not None else "")
    df["_fecha_parsed"] = df[col["fecha"]].apply(_parse_fecha)
    df["_litros_f"] = df[col["litros"]].apply(_to_float)
    df["_importe_f"] = df[col["importe_total"]].apply(_to_float)

    prov_col = col.get("proveedor")
    est_col = col.get("estacion")
    if prov_col:
        df["_proveedor_str"] = df[str(prov_col)].apply(lambda x: str(x).strip() if x is not None else "")
    elif est_col:
        df["_proveedor_str"] = df[str(est_col)].apply(lambda x: str(x).strip() if x is not None else "")
    else:
        df["_proveedor_str"] = ""

    km_col = col.get("kilometros")
    if km_col:
        df["_km_f"] = df[str(km_col)].apply(_to_float)
    else:
        df["_km_f"] = None

    df = df[df["_mat_key"].astype(str).str.len() > 0]  # type: ignore[union-attr]
    df = df[df["_fecha_parsed"].notna()]  # type: ignore[union-attr]
    total_filas_leidas = int(len(df))
    if df.empty:
        raise ValueError("No hay filas válidas tras normalización")

    eid = str(empresa_id)

    q = filter_not_deleted(
        db.table("flota").select("id,matricula,certificacion_emisiones,odometro_actual").eq("empresa_id", eid)
    )
    res: Any = await db.execute(q)
    flota_rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []

    flota_map: dict[str, dict[str, Any]] = {}
    for r in flota_rows:
        try:
            mk = _norm_matricula_key(r.get("matricula"))
            if mk and mk not in flota_map:
                odo = r.get("odometro_actual")
                try:
                    odo_i = int(odo) if odo is not None else 0
                except (TypeError, ValueError):
                    odo_i = 0
                flota_map[mk] = {
                    "vehiculo_id": str(r.get("id")).strip(),
                    "certificacion_emisiones": r.get("certificacion_emisiones"),
                    "odometro_actual": odo_i,
                }
        except Exception:
            continue

    errores: list[str] = []
    filas_ok = 0
    total_litros = 0.0
    total_euros = 0.0
    total_co2_kg = 0.0

    for row in df.to_dict(orient="records"):
        mk = str(row.get("_mat_key") or "").strip()
        display_mat = str(row.get("_mat_display") or mk or "?").strip() or mk
        if not mk:
            errores.append("Fila sin matrícula válida.")
            continue

        vm = flota_map.get(mk)
        if not isinstance(vm, dict):
            errores.append(f"Matrícula «{display_mat}» no encontrada en la flota.")
            continue

        vehiculo_id = vm.get("vehiculo_id")
        if not vehiculo_id:
            errores.append(f"Matrícula «{display_mat}» no encontrada en la flota.")
            continue

        fd = row.get("_fecha_parsed")
        if not isinstance(fd, date):
            errores.append(f"Fila (matrícula «{display_mat}»): fecha inválida.")
            continue

        litros = float(row.get("_litros_f") or 0.0)
        if litros <= 0:
            errores.append(f"Fila «{display_mat}» {fd.isoformat()}: litros debe ser > 0.")
            continue

        importe_f = float(row.get("_importe_f") or 0.0)
        if importe_f <= 0:
            errores.append(f"Fila «{display_mat}» {fd.isoformat()}: importe total inválido o cero.")
            continue

        prov_raw = str(row.get("_proveedor_str") or "").strip()
        proveedor = prov_raw if prov_raw else "Combustible"
        concepto = f"Combustible {proveedor} ({mk})"[:2000]

        created = await gastos_service.create_gasto(
            empresa_id=eid,
            empleado=username_empleado,
            gasto_in=GastoCreate(
                proveedor=proveedor,
                fecha=fd,
                total_chf=importe_f,
                categoria="Combustible",
                concepto=concepto,
                moneda="EUR",
                nif_proveedor=None,
                iva=None,
                total_eur=importe_f,
            ),
            evidencia_bytes=None,
            evidencia_filename=None,
            evidencia_content_type=None,
        )

        await db.execute(
            db.table("gastos_vehiculo").insert(
                {
                    "empresa_id": eid,
                    "vehiculo_id": vehiculo_id,
                    "gasto_id": created.id,
                    "fecha": fd.isoformat(),
                    "categoria": "Combustible",
                    "proveedor": proveedor,
                    "estacion": prov_raw or None,
                    "matricula_normalizada": mk,
                    "litros": litros,
                    "importe_total": importe_f,
                    "moneda": "EUR",
                    "concepto": concepto,
                }
            )
        )

        # CO2: el trigger ``trg_esg_auditoria_calc_co2`` recalcula ``co2_emitido_kg`` en INSERT.
        ins_esg = await db.execute(
            db.table("esg_auditoria")
            .insert(
                {
                    "empresa_id": eid,
                    "vehiculo_id": vehiculo_id,
                    "gasto_id": str(created.id),
                    "fecha": fd.isoformat(),
                    "litros_consumidos": litros,
                    "tipo_combustible": "Diesel A",
                }
            )
            .select("co2_emitido_kg")
        )
        esg_data = getattr(ins_esg, "data", None)
        co2_fila = 0.0
        if isinstance(esg_data, list) and esg_data:
            try:
                co2_fila = float(esg_data[0].get("co2_emitido_kg") or 0)
            except (TypeError, ValueError):
                co2_fila = 0.0
        total_co2_kg += co2_fila

        km_val = row.get("_km_f")
        if km_val is not None and not (isinstance(km_val, float) and pd.isna(km_val)):  # type: ignore[arg-type]
            try:
                km_int = int(round(float(km_val)))
                cur_odo = int(vm.get("odometro_actual") or 0)
                if km_int > cur_odo:
                    await db.execute(
                        db.table("flota")
                        .update({"odometro_actual": km_int})
                        .eq("id", vehiculo_id)
                        .eq("empresa_id", eid)
                    )
                    vm["odometro_actual"] = km_int
                    flota_map[mk] = vm
            except (TypeError, ValueError) as exc:
                _log.debug("odometro skip fila %s: %s", display_mat, exc)

        filas_ok += 1
        total_litros += litros
        total_euros += importe_f

    return FuelImportResult(
        total_filas_leidas=total_filas_leidas,
        filas_importadas_ok=filas_ok,
        total_litros=round(total_litros, 4),
        total_euros=round(total_euros, 2),
        total_co2_kg=round(total_co2_kg, 6),
        errores=errores,
    )
