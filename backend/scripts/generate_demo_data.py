"""
Genera datos de demostración coherentes (12 meses) para una empresa de muestra:
portes, gastos (combustible ~30% del ingreso neto de portes), facturas encadenadas
VeriFactu (F1 + 2 rectificativas R1), huella CO₂ en portes (kg/km según normativa).

Persistencia: ``get_session_factory()`` (``SessionLocal``) + SQL parametrizado sobre el esquema
``public``. Los modelos Pydantic de dominio (p. ej. ``app.models.vehiculo``) orientan tipos y
normativas; no hay mapeadores ORM declarados para ``portes``/``facturas`` en el repositorio.

Requisitos: ``DATABASE_URL`` (Postgres). Para borrar facturas selladas hace falta un rol
con permisos adecuados (p. ej. ``service_role``), alineado con los triggers de inmutabilidad.

Uso:
  python scripts/generate_demo_data.py
  python scripts/generate_demo_data.py --reset
  python scripts/generate_demo_data.py --empresa-id <uuid> --reset
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

_ENV_FILE = BACKEND_ROOT / ".env"
if _ENV_FILE.exists():
    _env_map = dotenv_values(_ENV_FILE)
    for _k, _v in _env_map.items():
        if _k and _v is not None and not os.getenv(_k):
            os.environ[_k] = _v

from app.core.math_engine import negate_fiat_for_rectificativa
from app.core.verifactu import GENESIS_HASH, generate_invoice_hash
from app.db.session import get_engine, get_session_factory
from app.models.vehiculo import EngineClass, FuelType, NormativaEuro
_NORM_TO_ENGINE: dict[str, str] = {
    NormativaEuro.EURO_VI.value: EngineClass.EURO_VI.value,
    NormativaEuro.EURO_V.value: EngineClass.EURO_V.value,
    NormativaEuro.EURO_IV.value: EngineClass.EURO_IV.value,
    NormativaEuro.EURO_III.value: EngineClass.EURO_III.value,
}

DEMO_EMPRESA_CODE = "DEMO-DASHBOARD-001"
DEMO_EMPRESA_UUID = str(uuid5(NAMESPACE_URL, DEMO_EMPRESA_CODE))
DEMO_NIF = "B99887766"
IVA_RATE = Decimal("0.21")
NUM_PORTES = 50
DEMO_TAG = "demo_generate_script_v1"

# Rutas realistas (España / frontera). Varias se repetirán para cumplir n>=2 portes por ruta (Matriz CIP).
ROUTES: list[tuple[str, str, float]] = [
    ("Madrid, España", "Barcelona, España", 620.0),
    ("Valencia, España", "Bilbao, España", 580.0),
    ("Sevilla, España", "Málaga, España", 210.0),
    ("Zaragoza, España", "Pamplona, España", 180.0),
    ("Murcia, España", "Alicante, España", 85.0),
    ("Vigo, España", "A Coruña, España", 155.0),
    ("Gijón, España", "Santander, España", 195.0),
    ("Toledo, España", "Madrid, España", 75.0),
    ("Tarragona, España", "Barcelona, España", 95.0),
    ("Badajoz, España", "Lisboa, Portugal", 220.0),
    ("Logroño, España", "Burgos, España", 115.0),
    ("Granada, España", "Córdoba, España", 160.0),
    ("Almería, España", "Murcia, España", 220.0),
    ("Lleida, España", "Zaragoza, España", 150.0),
    ("Salamanca, España", "Valladolid, España", 125.0),
    ("Jaén, España", "Málaga, España", 210.0),
    ("Huelva, España", "Sevilla, España", 95.0),
    ("Castellón de la Plana, España", "Valencia, España", 75.0),
    ("Girona, España", "Perpiñán, Francia", 105.0),
    ("Vitoria-Gasteiz, España", "San Sebastián, España", 105.0),
]

# kg CO₂ por km (por normativa de vehículo asignado) — Euro VI más bajo, Euro III ~0.9 (camión pesado).
CO2_KG_PER_KM: dict[str, float] = {
    NormativaEuro.EURO_VI.value: 0.48,
    NormativaEuro.EURO_V.value: 0.62,
    NormativaEuro.EURO_IV.value: 0.78,
    NormativaEuro.EURO_III.value: 0.90,
}


def _q2(v: Decimal | float | int) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"))


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generar datos demo para dashboard / VeriFactu / Matriz CIP.")
    p.add_argument(
        "--empresa-id",
        default=DEMO_EMPRESA_UUID,
        help=f"UUID empresa destino (default: demo fijo {DEMO_EMPRESA_CODE}).",
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="Elimina datos existentes de la empresa demo (portes, gastos, facturas, flota, clientes) antes de insertar.",
    )
    p.add_argument("--seed", type=int, default=20260413, help="Semilla RNG reproducible.")
    return p.parse_args()


def _month_keys_last_12(hoy: date) -> list[str]:
    y, m = hoy.year, hoy.month
    out: list[str] = []
    for _ in range(12):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    out.reverse()
    return out


def _pick_date_in_last_12m(
    rng: random.Random,
    *,
    hoy: date,
    month_weights: dict[str, float],
) -> date:
    """Distribución con estacionalidad (picos Q4) y ligero crecimiento hacia el presente."""
    keys = _month_keys_last_12(hoy)
    weights = [max(0.05, float(month_weights.get(k, 1.0))) for k in keys]
    s = sum(weights)
    weights = [w / s for w in weights]
    r = rng.random()
    acc = 0.0
    chosen = keys[-1]
    for k, w in zip(keys, weights, strict=True):
        acc += w
        if r <= acc:
            chosen = k
            break
    yy, mm = int(chosen[:4]), int(chosen[5:7])
    last = (date(yy + 1, 1, 1) - timedelta(days=1)) if mm == 12 else date(yy, mm + 1, 1) - timedelta(days=1)
    d1 = date(yy, mm, 1)
    return d1 + timedelta(days=rng.randint(0, max(0, (last - d1).days)))


def _seasonal_month_weights(hoy: date) -> dict[str, float]:
    """Peso relativo por mes (picos en nov-dic, valle en agosto)."""
    keys = _month_keys_last_12(hoy)
    out: dict[str, float] = {}
    for k in keys:
        mm = int(k[5:7])
        # sinusoidal + Q4 bump
        base = 0.85 + 0.15 * math.sin((mm - 1) * math.pi / 6.0)
        if mm in (11, 12):
            base += 0.35
        if mm == 8:
            base -= 0.22
        out[k] = max(0.2, base)
    return out


def _reset_demo_data(session: Session, empresa_id: str) -> None:
    eid = str(empresa_id)

    def _try(sql: str) -> None:
        try:
            session.execute(text(sql), {"eid": eid})
        except Exception:
            session.rollback()

    # Primero tablas dependientes de facturas (pueden no existir en todos los entornos).
    _try(
        """
        DELETE FROM public.verifactu_envios
        WHERE factura_id IN (SELECT id FROM public.facturas WHERE empresa_id = CAST(:eid AS uuid))
        """
    )
    _try(
        """
        DELETE FROM public.movimientos_bancarios
        WHERE empresa_id = CAST(:eid AS uuid)
           OR factura_id IN (SELECT id FROM public.facturas WHERE empresa_id = CAST(:eid AS uuid))
        """
    )
    _try("DELETE FROM public.bank_transactions WHERE empresa_id = CAST(:eid AS uuid)")

    session.execute(text("DELETE FROM public.portes WHERE empresa_id = CAST(:eid AS uuid)"), {"eid": eid})
    session.execute(text("DELETE FROM public.gastos WHERE empresa_id = CAST(:eid AS uuid)"), {"eid": eid})
    session.execute(
        text(
            """
            DELETE FROM public.facturas
            WHERE empresa_id = CAST(:eid AS uuid)
              AND COALESCE(tipo_factura, '') = 'R1'
            """
        ),
        {"eid": eid},
    )
    session.execute(text("DELETE FROM public.facturas WHERE empresa_id = CAST(:eid AS uuid)"), {"eid": eid})
    session.execute(text("DELETE FROM public.flota WHERE empresa_id = CAST(:eid AS uuid)"), {"eid": eid})
    session.execute(text("DELETE FROM public.clientes WHERE empresa_id = CAST(:eid AS uuid)"), {"eid": eid})
    session.commit()


def _ensure_empresa(session: Session, empresa_id: str) -> str:
    row = session.execute(
        text("SELECT id FROM public.empresas WHERE id = CAST(:id AS uuid) LIMIT 1"),
        {"id": empresa_id},
    ).fetchone()
    if row:
        return str(row[0])
    session.execute(
        text(
            """
            INSERT INTO public.empresas (id, nombre_comercial, nombre_legal, nif, plan)
            VALUES (CAST(:id AS uuid), :nc, :nl, :nif, :plan)
            """
        ),
        {
            "id": empresa_id,
            "nc": DEMO_EMPRESA_CODE,
            "nl": "Demo Dashboard Transport S.L.",
            "nif": DEMO_NIF,
            "plan": "Enterprise",
        },
    )
    session.commit()
    return empresa_id


def _insert_clientes(session: Session, empresa_id: str) -> list[str]:
    specs = [
        ("Retail Norte S.A.", "A11223344", "cliente.norte@demo.local"),
        ("Industria Sur S.L.", "B22334455", "logistica.sur@demo.local"),
        ("Fresh Food Iberia", "B33445566", "ops@freshfood.demo.local"),
    ]
    out: list[str] = []
    for nombre, nif, email in specs:
        cid = str(uuid4())
        session.execute(
            text(
                """
                INSERT INTO public.clientes (id, empresa_id, nombre, nif, email, telefono, direccion)
                VALUES (CAST(:id AS uuid), CAST(:eid AS uuid), :nombre, :nif, :email, :tel, :dir)
                """
            ),
            {
                "id": cid,
                "eid": empresa_id,
                "nombre": nombre,
                "nif": nif,
                "email": email,
                "tel": "+34 900 000 000",
                "dir": "Calle Demo 1, Madrid",
            },
        )
        out.append(cid)
    session.commit()
    return out


def _insert_flota(session: Session, empresa_id: str) -> list[tuple[str, str, float]]:
    """
    5 vehículos con perfiles distintos (Matriz CIP: mezcla Euro VI vs motores antiguos).
    Retorna lista (id, normativa_euro, kg_co2_por_km).
    """
    specs: list[tuple[str, NormativaEuro, str]] = [
        ("DEM01ABC", NormativaEuro.EURO_VI, "Scania R450 EURO VI"),
        ("DEM02ABC", NormativaEuro.EURO_VI, "Volvo FH EURO VI"),
        ("DEM03ABC", NormativaEuro.EURO_V, "MAN TGX EURO V"),
        ("DEM04ABC", NormativaEuro.EURO_IV, "Iveco Stralis EURO IV"),
        ("DEM05ABC", NormativaEuro.EURO_III, "Mercedes Actros EURO III"),
    ]
    out: list[tuple[str, str, float]] = []
    for mat, norm, label in specs:
        vid = str(uuid4())
        ne = norm.value
        session.execute(
            text(
                """
                INSERT INTO public.flota (
                  id, empresa_id, vehiculo, matricula, precio_compra, km_actual, estado,
                  tipo_motor, certificacion_emisiones, normativa_euro,
                  engine_class, fuel_type,
                  km_proximo_servicio, itv_vencimiento, seguro_vencimiento
                )
                VALUES (
                  CAST(:id AS uuid), CAST(:eid AS uuid), :veh, :mat, 78000, 140000, 'Operativo',
                  'Diesel', :cert, :ne,
                  :eng, :fuel,
                  180000, :itv, :seg
                )
                """
            ),
            {
                "id": vid,
                "eid": empresa_id,
                "veh": label,
                "mat": mat,
                "cert": ne,
                "ne": ne,
                "eng": _NORM_TO_ENGINE.get(ne, EngineClass.EURO_VI.value),
                "fuel": FuelType.DIESEL.value,
                "itv": (date.today() + timedelta(days=200)).isoformat(),
                "seg": (date.today() + timedelta(days=120)).isoformat(),
            },
        )
        out.append((vid, ne, CO2_KG_PER_KM[ne]))
    session.commit()
    return out


def _build_porte_plan(
    rng: random.Random,
    *,
    hoy: date,
    cliente_ids: list[str],
    vehiculos: list[tuple[str, str, float]],
) -> list[dict[str, Any]]:
    """~50 portes con rutas repetidas (>=2 por ruta clave) y tendencia de precio/km."""
    mw = _seasonal_month_weights(hoy)
    # Forzar duplicados explícitos para CIP (>=2 portes por misma ruta): 18×2 + 14 = 50
    route_sequence: list[tuple[str, str, float]] = []
    for r in ROUTES[:18]:
        route_sequence.extend([r, r])
    route_sequence.extend(ROUTES[:14])  # 36+14 = 50
    route_sequence = route_sequence[:NUM_PORTES]

    portes: list[dict[str, Any]] = []
    # Índice de "mes" 0..11 para tendencia de crecimiento de tarifa
    keys = _month_keys_last_12(hoy)
    key_index = {k: i for i, k in enumerate(keys)}

    for i, (orig, dest, km_base) in enumerate(route_sequence):
        cid = cliente_ids[i % len(cliente_ids)]
        vid, norm, co2_km = vehiculos[i % len(vehiculos)]
        fecha = _pick_date_in_last_12m(rng, hoy=hoy, month_weights=mw)
        mk = f"{fecha.year:04d}-{fecha.month:02d}"
        growth = 1.0 + 0.04 * (key_index.get(mk, 6) / 11.0)  # ~4% más tarifa al final de ventana
        seasonal = 1.0 + 0.06 * math.sin((fecha.month - 1) * math.pi / 6.0)
        km_noise = 0.92 + rng.random() * 0.16
        km = max(40.0, float(_q2(km_base * km_noise)))
        km_vacio = float(_q2(km * (0.08 + rng.random() * 0.12)))
        precio = float(
            _q2(Decimal(str(km)) * Decimal("1.15") * Decimal(str(growth)) * Decimal(str(seasonal)) + Decimal(str(rng.uniform(35, 120))))
        )
        bultos = 8 + (i % 18)
        peso = float(_q2(Decimal("4.5") + Decimal(str((i % 8))) * Decimal("1.25")))
        co2_kg = float(_q2(Decimal(str(km)) * Decimal(str(co2_km))))

        portes.append(
            {
                "cliente_id": cid,
                "fecha": fecha,
                "origen": orig,
                "destino": dest,
                "km_estimados": km,
                "km_vacio": km_vacio,
                "bultos": bultos,
                "peso_ton": peso,
                "descripcion": f"{DEMO_TAG} · ruta programada ({norm})",
                "precio_pactado": precio,
                "vehiculo_id": vid,
                "normativa": norm,
                "co2_kg": co2_kg,
                "co2_emitido": co2_kg,
                "estado": "facturado",
            }
        )
    return portes


def _invoice_hash_chain(
    *,
    nif_emisor: str,
    rows_spec: list[dict[str, Any]],
    seq_start: int,
    prev_hash: str,
) -> list[dict[str, Any]]:
    """Construye filas F1 con hash encadenado (misma lógica que seed_sandbox)."""
    chain_prev = prev_hash
    built: list[dict[str, Any]] = []
    for i, spec in enumerate(rows_spec):
        seq = seq_start + i
        base = _q2(spec["base"])
        iva = _q2(base * IVA_RATE)
        total = _q2(base + iva)
        fecha = spec["fecha_emision"]
        num = spec["num_factura"]
        h = generate_invoice_hash(
            {
                "numero_factura": num,
                "fecha_emision": fecha,
                "nif_emisor": nif_emisor,
                "nif_receptor": spec["nif_receptor"],
                "total_factura": float(total),
            },
            chain_prev,
        )
        row = {
            "empresa_id": spec["empresa_id"],
            "cliente": spec["cliente"],
            "num_factura": num,
            "numero_factura": num,
            "fecha_emision": fecha,
            "fecha_expedicion": fecha,
            "tipo_factura": "F1",
            "nif_emisor": nif_emisor,
            "base_imponible": float(base),
            "cuota_iva": float(iva),
            "total_factura": float(total),
            "numero_secuencial": seq,
            "hash_anterior": chain_prev,
            "hash_registro": h,
            "hash_factura": h,
            "huella_anterior": chain_prev,
            "huella_hash": h,
            "estado_cobro": spec.get("estado_cobro", "emitida"),
            "aeat_sif_estado": spec.get("aeat_sif_estado", "aceptado"),
            "total_km_estimados_snapshot": float(spec["km_snapshot"]),
            "payment_status": "PENDING",
        }
        built.append(row)
        chain_prev = h
    return built


def _fetch_next_sequential(session: Session, empresa_id: str) -> tuple[int, str]:
    row = session.execute(
        text(
            """
            SELECT numero_secuencial, hash_registro
            FROM public.facturas
            WHERE empresa_id = CAST(:eid AS uuid)
            ORDER BY numero_secuencial DESC NULLS LAST
            LIMIT 1
            """
        ),
        {"eid": empresa_id},
    ).fetchone()
    if not row or row[0] is None:
        return 1, GENESIS_HASH
    last_seq = int(row[0] or 0)
    last_hash = str(row[1] or "").strip() or GENESIS_HASH
    return last_seq + 1, last_hash


def _insert_facturas_f1(session: Session, rows: list[dict[str, Any]]) -> list[int]:
    ids: list[int] = []
    for row in rows:
        r = session.execute(
            text(
                """
                INSERT INTO public.facturas (
                  empresa_id, cliente, num_factura, numero_factura,
                  fecha_emision, fecha_expedicion, tipo_factura, nif_emisor,
                  base_imponible, cuota_iva, total_factura,
                  numero_secuencial, hash_anterior, hash_registro, hash_factura,
                  huella_anterior, huella_hash,
                  estado_cobro, aeat_sif_estado, total_km_estimados_snapshot, payment_status
                ) VALUES (
                  CAST(:empresa_id AS uuid), CAST(:cliente AS uuid), :num_factura, :numero_factura,
                  CAST(:fecha_emision AS date), CAST(:fecha_expedicion AS date), :tipo_factura, :nif_emisor,
                  :base_imponible, :cuota_iva, :total_factura,
                  :numero_secuencial, :hash_anterior, :hash_registro, :hash_factura,
                  :huella_anterior, :huella_hash,
                  :estado_cobro, :aeat_sif_estado, :total_km_estimados_snapshot, :payment_status
                )
                RETURNING id
                """
            ),
            {k: row[k] for k in row},
        ).fetchone()
        if not r:
            raise RuntimeError("Inserción de factura sin id")
        ids.append(int(r[0]))
    session.commit()
    return ids


def _insert_r1_pair(
    session: Session,
    *,
    empresa_id: str,
    nif_emisor: str,
    nif_cliente: str,
    orig_row: dict[str, Any],
    orig_id: int,
    seq: int,
    hash_prev_chain: str,
    motivo: str,
) -> tuple[int, str]:
    """Inserta una rectificativa R1 (importes negativos) con huella VeriFactu."""
    fecha_iso = str(date.today().isoformat())
    num_r = f"R-{date.today().year}-{seq:06d}"
    base_r = float(negate_fiat_for_rectificativa(orig_row["base_imponible"]))
    cuota_r = float(negate_fiat_for_rectificativa(orig_row["cuota_iva"]))
    total_r = float(negate_fiat_for_rectificativa(orig_row["total_factura"]))

    if not str(orig_row.get("hash_registro") or orig_row.get("hash_factura") or "").strip():
        raise RuntimeError("F1 original sin hash_registro; no se puede generar R1 demo")

    # Cadena: mismo `generate_invoice_hash` que F1 (app.core.verifactu), encadenado al último registro.
    h_chain = generate_invoice_hash(
        {
            "numero_factura": num_r,
            "fecha_emision": fecha_iso,
            "nif_emisor": nif_emisor,
            "nif_receptor": nif_cliente,
            "total_factura": float(total_r),
        },
        hash_prev_chain,
    )

    ins = session.execute(
        text(
            """
            INSERT INTO public.facturas (
              empresa_id, cliente, num_factura, numero_factura,
              fecha_emision, fecha_expedicion, tipo_factura, nif_emisor,
              base_imponible, cuota_iva, total_factura,
              numero_secuencial, hash_anterior, hash_registro, hash_factura,
              huella_anterior, huella_hash,
              estado_cobro, aeat_sif_estado, total_km_estimados_snapshot,
              factura_rectificada_id, motivo_rectificacion, payment_status
            ) VALUES (
              CAST(:empresa_id AS uuid), CAST(:cliente AS uuid), :num_factura, :numero_factura,
              CAST(:fecha_emision AS date), CAST(:fecha_expedicion AS date), :tipo_factura, :nif_emisor,
              :base_imponible, :cuota_iva, :total_factura,
              :numero_secuencial, :hash_anterior, :hash_registro, :hash_factura,
              :huella_anterior, :huella_hash,
              :estado_cobro, :aeat_sif_estado, :total_km_estimados_snapshot,
              :factura_rectificada_id, :motivo_rectificacion, :payment_status
            )
            RETURNING id
            """
        ),
        {
            "empresa_id": empresa_id,
            "cliente": orig_row["cliente"],
            "num_factura": num_r,
            "numero_factura": num_r,
            "fecha_emision": fecha_iso,
            "fecha_expedicion": fecha_iso,
            "tipo_factura": "R1",
            "nif_emisor": nif_emisor,
            "base_imponible": base_r,
            "cuota_iva": cuota_r,
            "total_factura": total_r,
            "numero_secuencial": seq,
            "hash_anterior": hash_prev_chain,
            "hash_registro": h_chain,
            "hash_factura": h_chain,
            "huella_anterior": hash_prev_chain,
            "huella_hash": h_chain,
            "estado_cobro": "emitida",
            "aeat_sif_estado": "aceptado",
            "total_km_estimados_snapshot": float(orig_row.get("total_km_estimados_snapshot") or 0.0),
            "factura_rectificada_id": orig_id,
            "motivo_rectificacion": motivo,
            "payment_status": "PENDING",
        },
    ).fetchone()
    session.commit()
    new_id = int(ins[0]) if ins else 0
    return new_id, h_chain


def _insert_portes(
    session: Session,
    empresa_id: str,
    portes: list[dict[str, Any]],
    factura_ids: list[int],
) -> None:
    if len(portes) != len(factura_ids):
        raise ValueError("portes y facturas deben tener la misma longitud")
    for p, fid in zip(portes, factura_ids, strict=True):
        session.execute(
            text(
                """
                INSERT INTO public.portes (
                  id, empresa_id, cliente_id, fecha, origen, destino,
                  km_estimados, km_vacio, bultos, peso_ton, descripcion,
                  precio_pactado, vehiculo_id, estado, factura_id,
                  co2_kg, co2_emitido, subcontratado
                )
                VALUES (
                  gen_random_uuid(), CAST(:eid AS uuid), CAST(:cid AS uuid), CAST(:fecha AS date),
                  :origen, :destino, :km_estimados, :km_vacio, :bultos, :peso_ton, :descripcion,
                  :precio_pactado, CAST(:vid AS uuid), :estado, :factura_id,
                  :co2_kg, :co2_emitido, false
                )
                """
            ),
            {
                "eid": empresa_id,
                "cid": p["cliente_id"],
                "fecha": p["fecha"].isoformat(),
                "origen": p["origen"],
                "destino": p["destino"],
                "km_estimados": p["km_estimados"],
                "km_vacio": p["km_vacio"],
                "bultos": p["bultos"],
                "peso_ton": p["peso_ton"],
                "descripcion": p["descripcion"],
                "precio_pactado": p["precio_pactado"],
                "vid": p["vehiculo_id"],
                "estado": p["estado"],
                "factura_id": fid,
                "co2_kg": p["co2_kg"],
                "co2_emitido": p["co2_emitido"],
            },
        )
    session.commit()


def _insert_gastos(
    session: Session,
    empresa_id: str,
    *,
    total_revenue_net: Decimal,
    month_keys: list[str],
    rng: random.Random,
) -> None:
    """
    Reparte combustible (~30% del ingreso neto de portes), peajes y mantenimiento en el periodo.
    Los importes se guardan con IVA desglosado para que FinanceService calcule neto correctamente.
    """
    fuel_target = _q2(total_revenue_net * Decimal("0.30"))
    tolls_target = _q2(total_revenue_net * Decimal("0.08"))
    maint_target = _q2(total_revenue_net * Decimal("0.07"))

    def split_shares(n: int) -> list[float]:
        raw = [rng.random() + 0.2 for _ in range(n)]
        s = sum(raw)
        return [x / s for x in raw]

    shares = split_shares(len(month_keys))

    def emit_category(label: str, target: Decimal, cat: str) -> None:
        for mk, sh in zip(month_keys, shares, strict=True):
            net = _q2(target * Decimal(str(sh)))
            if net <= 0:
                continue
            iva = _q2(net * IVA_RATE)
            gross = _q2(net + iva)
            # repartir en 2-3 tickets por mes para variedad
            chunks = 2 if rng.random() > 0.4 else 3
            for chunk_i in range(chunks):
                part = _q2(net / Decimal(chunks))
                iva_p = _q2(part * IVA_RATE)
                gross_p = _q2(part + iva_p)
                y, m = int(mk[:4]), int(mk[5:7])
                d0 = date(y, m, 1)
                d1 = (date(y + 1, 1, 1) - timedelta(days=1)) if m == 12 else date(y, m + 1, 1) - timedelta(days=1)
                fday = d0 + timedelta(days=rng.randint(0, max(0, (d1 - d0).days)))
                session.execute(
                    text(
                        """
                        INSERT INTO public.gastos (
                          id, empresa_id, empleado, proveedor, fecha, categoria, concepto,
                          moneda, total_chf, total_eur, iva
                        )
                        VALUES (
                          gen_random_uuid(), CAST(:eid AS uuid), :emp, :prov, CAST(:fecha AS date),
                          :categoria, :concepto, 'EUR', :gross, :gross, :iva
                        )
                        """
                    ),
                    {
                        "eid": empresa_id,
                        "emp": "demo.script@abscanner.local",
                        "prov": f"Proveedor {label} {chunk_i+1:02d}",
                        "fecha": fday.isoformat(),
                        "categoria": cat,
                        "concepto": f"{DEMO_TAG} · {label}",
                        "gross": float(gross_p),
                        "iva": float(iva_p),
                    },
                )

    emit_category("Combustible", fuel_target, "Combustible")
    emit_category("Peajes", tolls_target, "Peajes")
    emit_category("Mantenimiento", maint_target, "Vehículo Mantenimiento")
    session.commit()


def main() -> None:
    args = _args()
    rng = random.Random(args.seed)
    hoy = date.today()

    eng = get_engine()
    if eng is None:
        raise SystemExit("DATABASE_URL no configurada: no se puede abrir SessionLocal.")

    sf = get_session_factory()
    if sf is None:
        raise SystemExit("SessionLocal no inicializado.")

    empresa_id = str(args.empresa_id).strip()

    with sf() as session:
        assert isinstance(session, Session)
        if args.reset:
            _reset_demo_data(session, empresa_id)

        _ensure_empresa(session, empresa_id)
        cliente_ids = _insert_clientes(session, empresa_id)
        vehiculos = _insert_flota(session, empresa_id)
        portes = _build_porte_plan(rng, hoy=hoy, cliente_ids=cliente_ids, vehiculos=vehiculos)

        total_rev = sum(Decimal(str(p["precio_pactado"])) for p in portes)
        seq_start, prev_hash = _fetch_next_sequential(session, empresa_id)

        # Pequeña mezcla de estados AEAT en F1 (la mayoría aceptadas).
        nif_clients = ["A11223344", "B22334455", "B33445566"]

        f1_specs: list[dict[str, Any]] = []
        for i, p in enumerate(portes):
            fe = p["fecha"].isoformat()
            nif_c = nif_clients[cliente_ids.index(p["cliente_id"]) % len(nif_clients)]
            st = "aceptado"
            if i % 17 == 0:
                st = "pendiente"
            elif i % 23 == 0:
                st = "enviado_ok"
            f1_specs.append(
                {
                    "empresa_id": empresa_id,
                    "cliente": p["cliente_id"],
                    "fecha_emision": fe,
                    "num_factura": f"{DEMO_EMPRESA_CODE}-{fe[:4]}-{seq_start + i:06d}",
                    "base": float(_q2(Decimal(str(p["precio_pactado"])))),
                    "nif_receptor": nif_c,
                    "km_snapshot": p["km_estimados"],
                    "aeat_sif_estado": st,
                }
            )

        f1_rows = _invoice_hash_chain(
            nif_emisor=DEMO_NIF,
            rows_spec=f1_specs,
            seq_start=seq_start,
            prev_hash=prev_hash,
        )
        f1_ids = _insert_facturas_f1(session, f1_rows)

        # Rectificativas R1 sobre dos F1 (últimas dos posiciones evitan solaparse con IDs recientes)
        idx_targets = [7, 19]
        last_row = f1_rows[-1]
        last_hash = str(last_row["hash_registro"])
        next_seq = seq_start + len(f1_rows)

        for j, idx_t in enumerate(idx_targets):
            orig_id = f1_ids[idx_t]
            # Re-leer F1 mínima para R1
            row = session.execute(
                text("SELECT * FROM public.facturas WHERE id = :id AND empresa_id = CAST(:eid AS uuid)"),
                {"id": orig_id, "eid": empresa_id},
            ).mappings().first()
            if not row:
                raise RuntimeError("No se encontró factura original para R1")
            orig_map = dict(row)
            nif_c = nif_clients[
                cliente_ids.index(str(orig_map.get("cliente"))) % len(nif_clients)
            ]
            new_id, h_new = _insert_r1_pair(
                session,
                empresa_id=empresa_id,
                nif_emisor=DEMO_NIF,
                nif_cliente=nif_c,
                orig_row=orig_map,
                orig_id=orig_id,
                seq=next_seq,
                hash_prev_chain=last_hash,
                motivo=f"Demo VeriFactu R1 #{j+1}: corrección base imponible ({DEMO_TAG})",
            )
            next_seq += 1
            last_hash = h_new
            _ = new_id

        _insert_portes(session, empresa_id, portes, f1_ids)

        _insert_gastos(
            session,
            empresa_id,
            total_revenue_net=total_rev,
            month_keys=_month_keys_last_12(hoy),
            rng=rng,
        )

    print(f"OK empresa_id={empresa_id}")
    print(f"  clientes={len(cliente_ids)} flota={len(vehiculos)} portes={len(portes)} facturas_F1={len(f1_ids)} rectificativas_R1=2")
    print(f"  ingreso_neto_portes_eur={float(_q2(total_rev)):.2f} combustible_objetivo_30%={float(_q2(total_rev*Decimal('0.30'))):.2f}")


if __name__ == "__main__":
    main()
