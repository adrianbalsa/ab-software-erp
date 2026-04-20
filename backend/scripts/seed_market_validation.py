"""
Poblado de datos para validación de mercado — Cuentas A (transportista), B (cargador), C (internacional).

Requisitos cubiertos:
  - Perfiles de volumen/temporalidad descritos en el plan de onboarding comercial.
  - Importes monetarios con ``ROUND_HALF_EVEN`` (vía ``quantize_currency`` / ``FinanceService``).
  - CO₂ diésel en portes: kg = litros × 2,67 (ISO 14083), cuantizado de forma estable.
  - Multi-tenant: todos los registros llevan ``empresa_id`` (RLS Supabase con JWT de empresa).

Ejecución:
  python backend/scripts/seed_market_validation.py
  python backend/scripts/seed_market_validation.py --reset   # borra datos previos de las 3 cuentas MV

  # Enlazar usuarios del portal (service_role; el trigger permite cambio de empresa_id):
  python backend/scripts/seed_market_validation.py --link-only \\
    --link-a-email admin-a@tu-dominio.com --link-b-email admin-b@tu-dominio.com \\
    --link-c-email admin-c@tu-dominio.com

  # Seed + enlace en un solo paso:
  python backend/scripts/seed_market_validation.py --reset \\
    --link-a-email admin-a@tu-dominio.com --profile-role admin

Notas:
  - Usa ``SUPABASE_SERVICE_KEY`` (bypass RLS solo en este job operativo).
  - Los emails deben coincidir con ``profiles.email`` (Auth/Supabase).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from dotenv import dotenv_values

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

_ENV_FILE = BACKEND_ROOT / ".env"
if _ENV_FILE.exists():
    for k, v in dotenv_values(_ENV_FILE).items():
        if k and v is not None and v != "" and not os.getenv(k):
            os.environ[k] = v

from app.core.constants import ISO_14083_DIESEL_CO2_KG_PER_LITRE
from app.core.math_engine import quantize_currency, to_decimal
from app.db.soft_delete import filter_not_deleted
from app.db.supabase import get_supabase
from app.services.bi_service import BiService
from app.services.finance_service import FinanceService

IVA_RATE = Decimal("0.21")
ISO_KG_PER_L = Decimal(str(ISO_14083_DIESEL_CO2_KG_PER_LITRE))

# UUIDs deterministas (misma empresa en cada entorno si se re-ejecuta el seed).
ACCOUNT_A_ID = str(uuid5(NAMESPACE_URL, "ab-scanner:market-validation:account-a:transportista"))
ACCOUNT_B_ID = str(uuid5(NAMESPACE_URL, "ab-scanner:market-validation:account-b:cargador"))
ACCOUNT_C_ID = str(uuid5(NAMESPACE_URL, "ab-scanner:market-validation:account-c:internacional"))

MV_TAG = "mv_seed_v1"


@dataclass(frozen=True, slots=True)
class GeoStamp:
    ciudad: str
    lat: float
    lng: float


# Geostamps en España (centros urbanos aprox.) para mapas de calor.
SPAIN_HUBS: list[GeoStamp] = [
    GeoStamp("Madrid", 40.4168, -3.7038),
    GeoStamp("Barcelona", 41.3874, 2.1686),
    GeoStamp("Valencia", 39.4699, -0.3763),
    GeoStamp("Sevilla", 37.3891, -5.9845),
    GeoStamp("Zaragoza", 41.6488, -0.8891),
    GeoStamp("Málaga", 36.7213, -4.4214),
    GeoStamp("Murcia", 37.9922, -1.1307),
    GeoStamp("Palma", 39.5696, 2.6502),
    GeoStamp("Las Palmas", 28.1236, -15.4366),
    GeoStamp("Bilbao", 43.2630, -2.9350),
    GeoStamp("Alicante", 38.3452, -0.4810),
    GeoStamp("Córdoba", 37.8882, -4.7794),
    GeoStamp("Valladolid", 41.6528, -4.7245),
    GeoStamp("Vigo", 42.2406, -8.7207),
    GeoStamp("Gijón", 43.5322, -5.6611),
    GeoStamp("A Coruña", 43.3623, -8.4115),
    GeoStamp("Vitoria-Gasteiz", 42.8467, -2.6719),
    GeoStamp("Granada", 37.1773, -3.5986),
    GeoStamp("Pamplona", 42.8125, -1.6458),
    GeoStamp("Santander", 43.4623, -3.8099),
]

INTL_DESTS: list[tuple[str, float, float]] = [
    ("Lyon, Francia", 45.7640, 4.8357),
    ("Milán, Italia", 45.4642, 9.1900),
    ("Rotterdam, Países Bajos", 51.9244, 4.4777),
    ("Hamburgo, Alemania", 53.5511, 9.9937),
    ("Oporto, Portugal", 41.1579, -8.6291),
]


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed market validation (cuentas A/B/C).")
    p.add_argument(
        "--reset",
        action="store_true",
        help="Elimina datos existentes de las tres empresas MV antes de insertar.",
    )
    p.add_argument("--seed", type=int, default=20260420, help="Semilla RNG reproducible.")
    p.add_argument(
        "--link-only",
        action="store_true",
        help="Solo enlaza perfiles a las empresas MV (no inserta portes/gastos).",
    )
    p.add_argument(
        "--link-a-email",
        default="",
        help="Email del usuario (profiles) para Cuenta A (transportista).",
    )
    p.add_argument(
        "--link-b-email",
        default="",
        help="Email del usuario para Cuenta B (cargador).",
    )
    p.add_argument(
        "--link-c-email",
        default="",
        help="Email del usuario para Cuenta C (internacional).",
    )
    p.add_argument(
        "--profile-role",
        default="admin",
        choices=("admin", "gestor", "transportista", "cliente", "developer", "superadmin"),
        help="Rol RBAC asignado al actualizar el perfil (default: admin).",
    )
    return p.parse_args()


def _chunked[T](items: list[T], size: int) -> list[list[T]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _jitter_coord(rng: random.Random, lat: float, lng: float, delta: float = 0.08) -> tuple[float, float]:
    return (
        round(lat + rng.uniform(-delta, delta), 5),
        round(lng + rng.uniform(-delta, delta), 5),
    )


def _gross_from_net(net: Decimal) -> tuple[float, float, float]:
    """Bruto + IVA desde neto (HALF_EVEN a céntimo)."""
    n = quantize_currency(net)
    iva = quantize_currency(n * IVA_RATE)
    gross = quantize_currency(n + iva)
    return float(gross), float(iva), float(n)


def _split_total_net(total: Decimal, n: int, rng: random.Random) -> list[Decimal]:
    """Reparte ``total`` en ``n`` importes netos que suman exactamente ``total`` (HALF_EVEN)."""
    if n <= 0:
        return []
    if n == 1:
        return [quantize_currency(total)]
    weights = [Decimal(str(rng.uniform(0.4, 1.6))) for _ in range(n)]
    wsum = sum(weights)
    parts: list[Decimal] = []
    acc = Decimal("0.00")
    for i, w in enumerate(weights[:-1]):
        part = quantize_currency(total * (w / wsum))
        parts.append(part)
        acc = quantize_currency(acc + part)
    parts.append(quantize_currency(total - acc))
    return parts


def _co2_kg_from_liters_diesel(liters: Decimal) -> float:
    kg = quantize_currency(liters * ISO_KG_PER_L)
    return float(kg)


def _ocr_concepto_stub(
    *,
    station: str,
    liters: float,
    gross: float,
    plate: str,
    idx: int,
) -> str:
    payload = {
        "source": "ocr_simulated",
        "confidence": round(0.88 + (idx % 10) * 0.01, 2),
        "station": station,
        "liters": liters,
        "total_eur": gross,
        "plate": plate,
        "engine": "diesel",
    }
    return f"{MV_TAG} | OCR | {json.dumps(payload, ensure_ascii=False)}"


async def _delete_mv_empresa(db: Any, empresa_id: str) -> None:
    eid = str(empresa_id)
    for table in (
        "gastos_vehiculo",
        "gastos",
        "portes",
        "flota",
        "vehiculos",
        "clientes",
    ):
        try:
            await db.execute(db.table(table).delete().eq("empresa_id", eid))
        except Exception:
            continue
    try:
        await db.execute(db.table("empresas").delete().eq("id", eid))
    except Exception:
        pass


async def _ensure_empresa(
    db: Any,
    *,
    empresa_id: str,
    nombre_comercial: str,
    nif: str,
    preferred_language: str,
) -> None:
    res: Any = await db.execute(db.table("empresas").select("id").eq("id", empresa_id).limit(1))
    rows = (res.data or []) if hasattr(res, "data") else []
    payload: dict[str, Any] = {
        "id": empresa_id,
        "nombre_comercial": nombre_comercial,
        "nombre_legal": f"{nombre_comercial} (Market Validation)",
        "nif": nif,
        "plan": "Enterprise",
    }
    if rows:
        await db.execute(
            db.table("empresas")
            .update({"preferred_language": preferred_language, "nombre_comercial": nombre_comercial})
            .eq("id", empresa_id)
        )
        return
    payload["preferred_language"] = preferred_language
    await db.execute(db.table("empresas").insert(payload))


async def _ensure_cliente(db: Any, empresa_id: str, *, nombre: str, email: str, nif: str) -> str:
    res: Any = await db.execute(
        db.table("clientes").select("id").eq("empresa_id", empresa_id).eq("email", email).limit(1)
    )
    rows = (res.data or []) if hasattr(res, "data") else []
    if rows:
        return str(rows[0]["id"])
    ins: Any = await db.execute(
        db.table("clientes").insert(
            {
                "empresa_id": empresa_id,
                "nombre": nombre,
                "nif": nif,
                "email": email,
                "telefono": "+34 900 000 000",
                "direccion": "Calle Market Validation 1",
            }
        )
    )
    out = (ins.data or []) if hasattr(ins, "data") else []
    if not out:
        raise RuntimeError(f"No se pudo crear cliente para empresa {empresa_id}")
    return str(out[0]["id"])


async def _insert_flota_unit(
    db: Any,
    *,
    empresa_id: str,
    flota_id: str,
    idx: int,
    plate: str,
    label: str,
    normativa: str,
) -> str:
    payload = {
        "id": flota_id,
        "empresa_id": empresa_id,
        "vehiculo": label,
        "matricula": plate,
        "precio_compra": float(quantize_currency(Decimal("72000") + Decimal(idx * 1200))),
        "km_actual": float(quantize_currency(Decimal("110000") + Decimal(idx * 4200))),
        "estado": "Operativo",
        "tipo_motor": "Diesel",
        "certificacion_emisiones": normativa,
        "normativa_euro": normativa,
        "km_proximo_servicio": float(quantize_currency(Decimal("160000") + Decimal(idx * 4200))),
        "itv_vencimiento": (date.today() + timedelta(days=160 + idx * 5)).isoformat(),
        "seguro_vencimiento": (date.today() + timedelta(days=130 + idx * 6)).isoformat(),
    }
    try:
        await db.execute(db.table("flota").insert(payload))
    except Exception:
        payload["normativa_euro"] = "Euro VI"
        payload["certificacion_emisiones"] = "Euro VI"
        await db.execute(db.table("flota").insert(payload))

    v_payload = {
        "id": flota_id,
        "empresa_id": empresa_id,
        "matricula": plate,
        "normativa_euro": normativa,
        "certificacion_emisiones": normativa,
    }
    try:
        await db.execute(db.table("vehiculos").insert(v_payload))
    except Exception:
        pass
    return flota_id


async def _seed_flota_batch(
    db: Any,
    empresa_id: str,
    *,
    count: int,
    prefix: str,
    rng: random.Random,
) -> list[str]:
    norms = ["Euro VI", "Euro V", "Euro IV", "Euro VI"]
    ids: list[str] = []
    for i in range(count):
        fid = str(uuid4())
        plate = f"{prefix}{i+1:02d}{rng.randint(10, 99)}XYZ"
        label = f"{prefix} Truck {i+1:02d}"
        await _insert_flota_unit(
            db,
            empresa_id=empresa_id,
            flota_id=fid,
            idx=i,
            plate=plate,
            label=label,
            normativa=norms[i % len(norms)],
        )
        ids.append(fid)
    return ids


def _random_date(rng: random.Random, d0: date, d1: date) -> date:
    span = max(0, (d1 - d0).days)
    return d0 + timedelta(days=rng.randint(0, span))


async def _insert_portes_chunked(db: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inserted: list[dict[str, Any]] = []
    for chunk in _chunked(rows, 25):
        res: Any = await db.execute(db.table("portes").insert(chunk))
        data = (res.data or []) if hasattr(res, "data") else []
        inserted.extend(list(data))
    return inserted


async def _reconcile_gastos_to_target_net(
    db: Any,
    *,
    empresa_id: str,
    target_total_net: Decimal,
    fecha: date,
) -> None:
    """Ajusta con un ticket adicional si la suma de netos persistidos difiere del objetivo (float/IVA)."""
    res: Any = await db.execute(
        filter_not_deleted(db.table("gastos").select("*").eq("empresa_id", empresa_id))
    )
    rows: list[dict[str, Any]] = (res.data or []) if hasattr(res, "data") else []
    actual = quantize_currency(
        sum(FinanceService._gasto_neto_sin_iva(r) for r in rows)
    )
    diff = quantize_currency(target_total_net - actual)
    if diff <= Decimal("0.00"):
        return
    gross, iva, _ = _gross_from_net(diff)
    await db.execute(
        db.table("gastos").insert(
            {
                "empresa_id": empresa_id,
                "empleado": "mv.seed@abscanner.local",
                "proveedor": "Ajuste contable seed",
                "fecha": fecha.isoformat(),
                "categoria": "otros",
                "concepto": f"{MV_TAG} · Ajuste HALF_EVEN cuadre ({diff})",
                "moneda": "EUR",
                "total_chf": gross,
                "total_eur": gross,
                "iva": iva,
            }
        )
    )


async def _insert_gastos_chunked(db: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inserted: list[dict[str, Any]] = []
    for chunk in _chunked(rows, 25):
        res: Any = await db.execute(db.table("gastos").insert(chunk))
        data = (res.data or []) if hasattr(res, "data") else []
        inserted.extend(list(data))
    return inserted


async def _insert_gastos_vehiculo_safe(db: Any, rows: list[dict[str, Any]]) -> int:
    n = 0
    for chunk in _chunked(rows, 20):
        try:
            res: Any = await db.execute(db.table("gastos_vehiculo").insert(chunk))
            data = (res.data or []) if hasattr(res, "data") else []
            n += len(data)
        except Exception:
            continue
    return n


async def _seed_account_transportista(db: Any, rng: random.Random) -> dict[str, Any]:
    eid = ACCOUNT_A_ID
    await _ensure_empresa(
        db,
        empresa_id=eid,
        nombre_comercial="MV · Cuenta A — Transportista",
        nif="B100000A1",
        preferred_language="es",
    )
    cliente_id = await _ensure_cliente(
        db, eid, nombre="Cliente Retail Nacional", email="mv-a-cliente@example.local", nif="A100000A1"
    )
    flota_ids = await _seed_flota_batch(db, eid, count=20, prefix="MVA", rng=rng)

    hoy = date.today()
    d_from = hoy - timedelta(days=75)
    porte_rows: list[dict[str, Any]] = []
    for i in range(120):
        o = SPAIN_HUBS[i % len(SPAIN_HUBS)]
        d = SPAIN_HUBS[(i + 3) % len(SPAIN_HUBS)]
        lo, go = _jitter_coord(rng, o.lat, o.lng)
        ld, gd = _jitter_coord(rng, d.lat, d.lng)
        km = float(quantize_currency(Decimal(str(rng.randint(120, 980)))))
        precio = float(
            quantize_currency(Decimal(str(km)) * Decimal("1.12") + Decimal(str(rng.randint(180, 520))))
        )
        liters = quantize_currency(Decimal(str(km)) * Decimal("0.28"))  # ~28 L/100km
        co2 = _co2_kg_from_liters_diesel(liters)
        fd = _random_date(rng, d_from, hoy)
        porte_rows.append(
            {
                "empresa_id": eid,
                "cliente_id": cliente_id,
                "fecha": fd.isoformat(),
                "origen": o.ciudad + ", España",
                "destino": d.ciudad + ", España",
                "km_estimados": km,
                "bultos": 8 + (i % 20),
                "peso_ton": float(quantize_currency(Decimal("6.5") + Decimal(i % 12) * Decimal("0.35"))),
                "descripcion": f"{MV_TAG} · Porte nacional #{i+1}",
                "precio_pactado": precio,
                "vehiculo_id": flota_ids[i % len(flota_ids)],
                "estado": "facturado",
                "lat_origin": lo,
                "lng_origin": go,
                "lat_dest": ld,
                "lng_dest": gd,
                "real_distance_meters": float(max(1000.0, km * 1000 * rng.uniform(0.92, 1.08))),
                "co2_emitido": co2,
                "co2_kg": co2,
            }
        )

    portes_ins = await _insert_portes_chunked(db, porte_rows)

    total_ing = quantize_currency(
        sum(quantize_currency(to_decimal(p["precio_pactado"])) for p in porte_rows)
    )
    target_margin = quantize_currency(total_ing * Decimal("0.21"))
    total_gas = quantize_currency(total_ing - target_margin)

    n_fuel = 95
    nets = _split_total_net(total_gas, n_fuel, rng)
    gasto_rows: list[dict[str, Any]] = []
    gv_rows: list[dict[str, Any]] = []
    stations = ("Repsol", "Cepsa", "BP", "Galp", "Shell")
    for j, net in enumerate(nets):
        gross, iva, _ = _gross_from_net(net)
        vid = flota_ids[j % len(flota_ids)]
        mat_row = await db.execute(
            filter_not_deleted(db.table("flota").select("matricula").eq("id", vid).limit(1))
        )
        mrows = (mat_row.data or []) if hasattr(mat_row, "data") else []
        plate = str(mrows[0].get("matricula") or "MVAX00") if mrows else "MVAX00"
        liters = float(quantize_currency(net / Decimal("1.455")))
        concepto = _ocr_concepto_stub(
            station=stations[j % len(stations)],
            liters=liters,
            gross=gross,
            plate=plate,
            idx=j,
        )
        fd = _random_date(rng, d_from, hoy)
        gid = str(uuid4())
        gasto_rows.append(
            {
                "id": gid,
                "empresa_id": eid,
                "empleado": "mv.seed@abscanner.local",
                "proveedor": f"{stations[j % len(stations)]} · OCR",
                "fecha": fd.isoformat(),
                "categoria": "combustible",
                "concepto": concepto,
                "moneda": "EUR",
                "total_chf": gross,
                "total_eur": gross,
                "iva": iva,
            }
        )
        gv_rows.append(
            {
                "empresa_id": eid,
                "vehiculo_id": vid,
                "gasto_id": gid,
                "fecha": fd.isoformat(),
                "categoria": "Combustible",
                "proveedor": stations[j % len(stations)],
                "estacion": stations[j % len(stations)],
                "matricula_normalizada": "".join(c for c in plate.upper() if c.isalnum()),
                "litros": liters,
                "importe_total": gross,
                "moneda": "EUR",
                "concepto": concepto[:240],
            }
        )

    await _insert_gastos_chunked(db, gasto_rows)
    await _reconcile_gastos_to_target_net(db, empresa_id=eid, target_total_net=total_gas, fecha=hoy)
    gv_n = await _insert_gastos_vehiculo_safe(db, gv_rows)

    return {
        "empresa_id": eid,
        "portes": len(portes_ins),
        "flota": len(flota_ids),
        "gastos_combustible": len(gasto_rows),
        "gastos_vehiculo": gv_n,
        "ingresos_portes_eur": float(total_ing),
        "gastos_net_target_eur": float(total_gas),
        "margen_objetivo_eur": float(target_margin),
    }


async def _seed_account_cargador(db: Any, rng: random.Random) -> dict[str, Any]:
    eid = ACCOUNT_B_ID
    await _ensure_empresa(
        db,
        empresa_id=eid,
        nombre_comercial="MV · Cuenta B — Cargador",
        nif="B200000B2",
        preferred_language="es",
    )
    cliente_id = await _ensure_cliente(
        db, eid, nombre="Shipper Iberia Consolidated", email="mv-b-shipper@example.local", nif="B200000B3"
    )
    flota_ids = await _seed_flota_batch(db, eid, count=8, prefix="MVB", rng=rng)

    hoy = date.today()
    d_from = hoy - timedelta(days=92)
    porte_rows: list[dict[str, Any]] = []
    for i in range(50):
        o = SPAIN_HUBS[(i * 2) % len(SPAIN_HUBS)]
        d = SPAIN_HUBS[(i * 2 + 5) % len(SPAIN_HUBS)]
        lo, go = _jitter_coord(rng, o.lat, o.lng, 0.05)
        ld, gd = _jitter_coord(rng, d.lat, d.lng, 0.05)
        km = float(quantize_currency(Decimal(str(rng.randint(95, 820)))))
        precio = float(quantize_currency(Decimal(str(km)) * Decimal("0.98") + Decimal(str(rng.randint(120, 380)))))
        liters = quantize_currency(Decimal(str(km)) * Decimal("0.26"))
        co2 = _co2_kg_from_liters_diesel(liters)
        fd = _random_date(rng, d_from, hoy)
        porte_rows.append(
            {
                "empresa_id": eid,
                "cliente_id": cliente_id,
                "fecha": fd.isoformat(),
                "origen": o.ciudad + ", España",
                "destino": d.ciudad + ", España",
                "km_estimados": km,
                "bultos": 6 + (i % 16),
                "peso_ton": float(quantize_currency(Decimal("5.2") + Decimal(i % 9) * Decimal("0.42"))),
                "descripcion": f"{MV_TAG} · Histórico cargador #{i+1}",
                "precio_pactado": precio,
                "vehiculo_id": flota_ids[i % len(flota_ids)],
                "estado": "entregado",
                "lat_origin": lo,
                "lng_origin": go,
                "lat_dest": ld,
                "lng_dest": gd,
                "real_distance_meters": float(max(1000.0, km * 1000 * rng.uniform(0.94, 1.06))),
                "co2_emitido": co2,
                "co2_kg": co2,
            }
        )

    portes_ins = await _insert_portes_chunked(db, porte_rows)
    total_ing = quantize_currency(
        sum(quantize_currency(to_decimal(p["precio_pactado"])) for p in porte_rows)
    )
    target_margin = quantize_currency(total_ing * Decimal("0.19"))
    total_gas = quantize_currency(total_ing - target_margin)

    comb_total = quantize_currency(total_gas * Decimal("0.62"))
    serv_total = quantize_currency(total_gas * Decimal("0.23"))
    otros_total = quantize_currency(total_gas - comb_total - serv_total)
    nets_comb = _split_total_net(comb_total, 18, rng)
    nets_serv = _split_total_net(serv_total, 10, rng)
    nets_otros = _split_total_net(otros_total, 8, rng)

    gasto_rows: list[dict[str, Any]] = []
    buckets: list[tuple[str, str]] = (
        [("combustible", "Red de combustible")] * len(nets_comb)
        + [("servicios", "Servicios logísticos")] * len(nets_serv)
        + [("materiales", "Mantenimiento programado")] * len(nets_otros)
    )
    for j, net in enumerate([*nets_comb, *nets_serv, *nets_otros]):
        gross, iva, _ = _gross_from_net(net)
        cat, prov = buckets[j]
        fd = _random_date(rng, d_from, hoy)
        gasto_rows.append(
            {
                "empresa_id": eid,
                "empleado": "mv.seed@abscanner.local",
                "proveedor": prov,
                "fecha": fd.isoformat(),
                "categoria": cat,
                "concepto": f"{MV_TAG} · Gasto operativo #{j+1}",
                "moneda": "EUR",
                "total_chf": gross,
                "total_eur": gross,
                "iva": iva,
            }
        )

    await _insert_gastos_chunked(db, gasto_rows)
    await _reconcile_gastos_to_target_net(db, empresa_id=eid, target_total_net=total_gas, fecha=hoy)

    return {
        "empresa_id": eid,
        "portes": len(portes_ins),
        "flota": len(flota_ids),
        "gastos": len(gasto_rows),
        "ingresos_portes_eur": float(total_ing),
        "gastos_net_target_eur": float(total_gas),
        "margen_objetivo_eur": float(target_margin),
    }


async def _seed_account_internacional(db: Any, rng: random.Random) -> dict[str, Any]:
    eid = ACCOUNT_C_ID
    await _ensure_empresa(
        db,
        empresa_id=eid,
        nombre_comercial="MV · Cuenta C — Internacional (EN)",
        nif="B300000C3",
        preferred_language="en",
    )
    cliente_id = await _ensure_cliente(
        db, eid, nombre="EU Logistics Partner GmbH", email="mv-c-eu@example.local", nif="DE300000C4"
    )
    flota_ids = await _seed_flota_batch(db, eid, count=4, prefix="MVC", rng=rng)

    hoy = date.today()
    d_from = hoy - timedelta(days=40)
    porte_rows: list[dict[str, Any]] = []
    for i in range(10):
        o = SPAIN_HUBS[(i + 4) % len(SPAIN_HUBS)]
        dest_label, dlat, dlng = INTL_DESTS[i % len(INTL_DESTS)]
        lo, go = _jitter_coord(rng, o.lat, o.lng)
        ld, gd = _jitter_coord(rng, dlat, dlng, 0.12)
        km = float(quantize_currency(Decimal(str(rng.randint(980, 1850)))))
        precio = float(quantize_currency(Decimal(str(km)) * Decimal("1.35") + Decimal("850")))
        liters = quantize_currency(Decimal(str(km)) * Decimal("0.38"))
        co2 = _co2_kg_from_liters_diesel(liters)
        fd = _random_date(rng, d_from, hoy)
        porte_rows.append(
            {
                "empresa_id": eid,
                "cliente_id": cliente_id,
                "fecha": fd.isoformat(),
                "origen": o.ciudad + ", España",
                "destino": dest_label,
                "km_estimados": km,
                "bultos": 12 + (i % 9),
                "peso_ton": float(quantize_currency(Decimal("14.5") + Decimal(i % 4) * Decimal("1.1"))),
                "descripcion": f"{MV_TAG} · International heavy lane #{i+1}",
                "precio_pactado": precio,
                "vehiculo_id": flota_ids[i % len(flota_ids)],
                "estado": "facturado",
                "lat_origin": lo,
                "lng_origin": go,
                "lat_dest": ld,
                "lng_dest": gd,
                "real_distance_meters": float(max(5000.0, km * 1000 * rng.uniform(0.96, 1.05))),
                "co2_emitido": co2,
                "co2_kg": co2,
            }
        )

    portes_ins = await _insert_portes_chunked(db, porte_rows)
    total_ing = quantize_currency(
        sum(quantize_currency(to_decimal(p["precio_pactado"])) for p in porte_rows)
    )
    target_margin = quantize_currency(total_ing * Decimal("0.24"))
    total_gas = quantize_currency(total_ing - target_margin)
    nets = _split_total_net(total_gas, 14, rng)
    gasto_rows: list[dict[str, Any]] = []
    for j, net in enumerate(nets):
        gross, iva, _ = _gross_from_net(net)
        cat = "combustible" if j % 2 == 0 else "servicios"
        fd = _random_date(rng, d_from, hoy)
        gasto_rows.append(
            {
                "empresa_id": eid,
                "empleado": "mv.seed@abscanner.local",
                "proveedor": "EU Diesel Network" if cat == "combustible" else "Toll Europe",
                "fecha": fd.isoformat(),
                "categoria": cat,
                "concepto": f"{MV_TAG} · Cross-border cost #{j+1}",
                "moneda": "EUR",
                "total_chf": gross,
                "total_eur": gross,
                "iva": iva,
            }
        )
    await _insert_gastos_chunked(db, gasto_rows)
    await _reconcile_gastos_to_target_net(db, empresa_id=eid, target_total_net=total_gas, fecha=hoy)

    return {
        "empresa_id": eid,
        "portes": len(portes_ins),
        "flota": len(flota_ids),
        "gastos": len(gasto_rows),
        "ingresos_portes_eur": float(total_ing),
        "gastos_net_target_eur": float(total_gas),
        "margen_objetivo_eur": float(target_margin),
        "co2_max_kg": max(float(p["co2_emitido"] or 0) for p in porte_rows),
    }


async def _verify_bi_margin(db: Any, empresa_id: str) -> tuple[float, float, float]:
    bi = BiService(db)
    hoy = date.today()
    rep = await bi.profit_margin_analytics(
        empresa_id=empresa_id,
        date_from=hoy - timedelta(days=400),
        date_to=hoy,
        granularity="month",
    )
    t = rep.totals_rango
    return t.ingresos_totales, t.gastos_totales, t.margen_neto


async def _verify_finance_month(db: Any, empresa_id: str) -> tuple[float, float, float]:
    fin = FinanceService(db)
    hoy = date.today()
    key = f"{hoy.year:04d}-{hoy.month:02d}"
    summ = await fin.financial_summary(empresa_id=empresa_id, period_month=key)
    return summ.ingresos, summ.gastos, summ.ebitda


async def _first_cliente_id_for_empresa(db: Any, empresa_id: str) -> str | None:
    try:
        res: Any = await db.execute(
            db.table("clientes").select("id").eq("empresa_id", empresa_id).limit(1)
        )
        rows = (res.data or []) if hasattr(res, "data") else []
        if not rows:
            return None
        cid = rows[0].get("id")
        return str(cid).strip() if cid else None
    except Exception:
        return None


async def _link_profile_email_to_empresa(
    db: Any,
    *,
    email: str,
    empresa_id: str,
    account_label: str,
    profile_role: str,
) -> None:
    """Actualiza ``profiles.empresa_id`` (y rol) vía service_role — permitido por el trigger de seguridad."""
    em = str(email or "").strip()
    if not em:
        return
    res: Any = await db.execute(
        db.table("profiles").select("id,email,empresa_id,role").eq("email", em).limit(1)
    )
    rows = (res.data or []) if hasattr(res, "data") else []
    if not rows:
        print(f"  [WARN] No hay perfil con email={em!r} (cuenta {account_label}).", file=sys.stderr)
        return
    row = rows[0]
    pid = str(row.get("id") or "").strip()
    if not pid:
        print(f"  [WARN] Perfil sin id para email={em!r}.", file=sys.stderr)
        return

    role_lc = str(profile_role or "admin").strip().lower()
    payload: dict[str, Any] = {
        "empresa_id": str(empresa_id).strip(),
        "role": role_lc,
    }
    if role_lc == "cliente":
        cid = await _first_cliente_id_for_empresa(db, str(empresa_id).strip())
        if cid:
            payload["cliente_id"] = cid
        else:
            print(
                f"  [WARN] Rol cliente sin filas en clientes para empresa {account_label}; "
                "se omite cliente_id.",
                file=sys.stderr,
            )

    try:
        upd: Any = await db.execute(
            db.table("profiles").update({**payload, "rol": role_lc}).eq("id", pid)
        )
        _ = upd
    except Exception:
        try:
            await db.execute(db.table("profiles").update(payload).eq("id", pid))
        except Exception as exc:
            print(f"  [ERROR] No se pudo actualizar perfil {pid} ({account_label}): {exc}", file=sys.stderr)
            return

    print(
        f"  [OK] Cuenta {account_label}: perfil id={pid} → empresa_id={empresa_id} role={role_lc} email={em}"
    )


async def _apply_profile_links(
    db: Any,
    *,
    link_a_email: str,
    link_b_email: str,
    link_c_email: str,
    profile_role: str,
) -> None:
    print("\n--- Enlace profiles → empresas MV (portal / RLS) ---")
    await _link_profile_email_to_empresa(
        db,
        email=link_a_email,
        empresa_id=ACCOUNT_A_ID,
        account_label="A",
        profile_role=profile_role,
    )
    await _link_profile_email_to_empresa(
        db,
        email=link_b_email,
        empresa_id=ACCOUNT_B_ID,
        account_label="B",
        profile_role=profile_role,
    )
    await _link_profile_email_to_empresa(
        db,
        email=link_c_email,
        empresa_id=ACCOUNT_C_ID,
        account_label="C",
        profile_role=profile_role,
    )


async def _mv_accounts_nonempty(db: Any) -> list[str]:
    found: list[str] = []
    for eid in (ACCOUNT_A_ID, ACCOUNT_B_ID, ACCOUNT_C_ID):
        try:
            res_p: Any = await db.execute(db.table("portes").select("id").eq("empresa_id", eid).limit(1))
            res_f: Any = await db.execute(db.table("flota").select("id").eq("empresa_id", eid).limit(1))
            p_rows = (res_p.data or []) if hasattr(res_p, "data") else []
            f_rows = (res_f.data or []) if hasattr(res_f, "data") else []
            if p_rows or f_rows:
                found.append(eid)
        except Exception:
            continue
    return found


async def main_async(args: argparse.Namespace) -> int:
    any_link = bool(
        (args.link_a_email or "").strip()
        or (args.link_b_email or "").strip()
        or (args.link_c_email or "").strip()
    )

    if args.link_only:
        if not any_link:
            print(
                "--link-only requiere al menos uno de: --link-a-email, --link-b-email, --link-c-email.",
                file=sys.stderr,
            )
            return 2
        db = await get_supabase(
            jwt_token=None,
            allow_service_role_bypass=True,
            log_service_bypass_warning=False,
        )
        await _apply_profile_links(
            db,
            link_a_email=args.link_a_email,
            link_b_email=args.link_b_email,
            link_c_email=args.link_c_email,
            profile_role=args.profile_role,
        )
        return 0

    rng = random.Random(args.seed)
    db = await get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )

    targets = (ACCOUNT_A_ID, ACCOUNT_B_ID, ACCOUNT_C_ID)
    if not args.reset:
        stale = await _mv_accounts_nonempty(db)
        if stale:
            print(
                "Ya existen portes para al menos una cuenta MV. "
                "Re-ejecuta con --reset para evitar duplicados, o asigna otra empresa.",
                file=sys.stderr,
            )
            return 2

    if args.reset:
        for eid in targets:
            await _delete_mv_empresa(db, eid)

    try:
        await db.rpc("set_empresa_context", {"p_empresa_id": ACCOUNT_A_ID})
    except Exception:
        pass

    summary_a = await _seed_account_transportista(db, rng)
    summary_b = await _seed_account_cargador(db, rng)
    summary_c = await _seed_account_internacional(db, rng)

    print("=== Market validation seed OK ===")
    for label, s in (("A Transportista", summary_a), ("B Cargador", summary_b), ("C Internacional", summary_c)):
        print(f"[{label}] empresa_id={s['empresa_id']} portes={s['portes']} flota={s['flota']}")
        extra = {k: v for k, v in s.items() if k not in ("empresa_id", "portes", "flota")}
        print(f"    {extra}")

    print("\n--- Verificación BI (ingresos portes − gastos netos, HALF_EVEN) ---")
    for eid, name in (
        (ACCOUNT_A_ID, "A"),
        (ACCOUNT_B_ID, "B"),
        (ACCOUNT_C_ID, "C"),
    ):
        ing, gas, mgn = await _verify_bi_margin(db, eid)
        ing_d = quantize_currency(to_decimal(ing))
        gas_d = quantize_currency(to_decimal(gas))
        mgn_d = quantize_currency(to_decimal(mgn))
        chk = quantize_currency(ing_d - gas_d)
        ok = mgn_d == chk
        print(f"  cuenta {name}: ing={float(ing_d):.2f} gas={float(gas_d):.2f} margen={float(mgn_d):.2f} cuadre={float(chk):.2f} ok={ok}")

    print("\n--- FinanceService mes actual (facturas − gastos; puede ser 0 si no hay facturas) ---")
    for eid, name in ((ACCOUNT_A_ID, "A"), (ACCOUNT_B_ID, "B"), (ACCOUNT_C_ID, "C")):
        ing, gas, ebit = await _verify_finance_month(db, eid)
        print(f"  cuenta {name}: ingresos_facturas={ing:.2f} gastos={gas:.2f} ebitda={ebit:.2f}")

    if any_link:
        await _apply_profile_links(
            db,
            link_a_email=args.link_a_email,
            link_b_email=args.link_b_email,
            link_c_email=args.link_c_email,
            profile_role=args.profile_role,
        )
    else:
        print(
            "\nTip: enlaza usuarios con --link-a-email / --link-b-email / --link-c-email "
            "o ejecuta --link-only tras el seed."
        )

    print(f"\nFactor CO₂ diésel referencia: {ISO_14083_DIESEL_CO2_KG_PER_LITRE} kg/L (ISO 14083).")
    return 0


def main() -> int:
    args = _args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
