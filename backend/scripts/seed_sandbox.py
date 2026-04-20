from __future__ import annotations

import argparse
import asyncio
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

ENV_FILE = BACKEND_ROOT / ".env"
if ENV_FILE.exists():
    env_map = dotenv_values(ENV_FILE)
    for k, v in env_map.items():
        if k and v is not None and not os.getenv(k):
            os.environ[k] = v

from app.core.verifactu import GENESIS_HASH
from app.core.verifactu_hashing import VerifactuCadena, generar_hash_factura_oficial
from app.db.supabase import SupabaseAsync, get_supabase
from app.services.finance_service import FinanceService
from app.services.maps_service import MapsService
from app.services.reconciliation_service import ReconciliationService

DEMO_EMPRESA_CODE = "DEMO-LOGISTICS-001"
DEMO_EMPRESA_UUID = str(uuid5(NAMESPACE_URL, DEMO_EMPRESA_CODE))
DEMO_NIF = "B76543210"
DEMO_CLIENT_EMAIL = "demo.cliente@demo-logistics.local"
IVA_RATE = Decimal("0.21")


@dataclass(slots=True)
class RouteSeed:
    origen: str
    destino: str


ROUTES: list[RouteSeed] = [
    RouteSeed("Madrid, España", "Barcelona, España"),
    RouteSeed("Valencia, España", "Zaragoza, España"),
    RouteSeed("Sevilla, España", "Málaga, España"),
    RouteSeed("Bilbao, España", "Valladolid, España"),
    RouteSeed("A Coruña, España", "Gijón, España"),
    RouteSeed("Murcia, España", "Alicante, España"),
    RouteSeed("Pamplona, España", "San Sebastián, España"),
    RouteSeed("León, España", "Salamanca, España"),
    RouteSeed("Burgos, España", "Logroño, España"),
    RouteSeed("Córdoba, España", "Granada, España"),
    RouteSeed("Almería, España", "Cartagena, España"),
    RouteSeed("Tarragona, España", "Lleida, España"),
    RouteSeed("Girona, España", "Perpiñán, Francia"),
    RouteSeed("Huesca, España", "Toulouse, Francia"),
    RouteSeed("Badajoz, España", "Lisboa, Portugal"),
    RouteSeed("Vigo, España", "Oporto, Portugal"),
    RouteSeed("Jaén, España", "Albacete, España"),
    RouteSeed("Cáceres, España", "Toledo, España"),
    RouteSeed("Santander, España", "Oviedo, España"),
    RouteSeed("Palencia, España", "Soria, España"),
    RouteSeed("Cuenca, España", "Teruel, España"),
    RouteSeed("Lugo, España", "Ourense, España"),
    RouteSeed("Huelva, España", "Cádiz, España"),
    RouteSeed("Jerez de la Frontera, España", "Mérida, España"),
    RouteSeed("Ciudad Real, España", "Talavera de la Reina, España"),
    RouteSeed("Castellón de la Plana, España", "Reus, España"),
    RouteSeed("Pontevedra, España", "Santiago de Compostela, España"),
    RouteSeed("Avilés, España", "Torrelavega, España"),
    RouteSeed("Benavente, España", "Aranda de Duero, España"),
    RouteSeed("Guadalajara, España", "Alcalá de Henares, España"),
    RouteSeed("Lorca, España", "Elche, España"),
    RouteSeed("Ceuta, España", "Algeciras, España"),
    RouteSeed("Mataró, España", "Manresa, España"),
    RouteSeed("Vitoria-Gasteiz, España", "Irun, España"),
    RouteSeed("Tudela, España", "Calahorra, España"),
    RouteSeed("Zamora, España", "Braganza, Portugal"),
    RouteSeed("Béjar, España", "Plasencia, España"),
    RouteSeed("Ronda, España", "Antequera, España"),
    RouteSeed("Andújar, España", "Úbeda, España"),
    RouteSeed("Denia, España", "Benidorm, España"),
    RouteSeed("Figueres, España", "Barcelona, España"),
    RouteSeed("Tarifa, España", "Málaga, España"),
    RouteSeed("Puertollano, España", "Valdepeñas, España"),
    RouteSeed("Arrecife, España", "Las Palmas de Gran Canaria, España"),
    RouteSeed("Santa Cruz de Tenerife, España", "San Cristóbal de La Laguna, España"),
    RouteSeed("Algeciras, España", "Sevilla, España"),
    RouteSeed("Linares, España", "Murcia, España"),
    RouteSeed("Talavera de la Reina, España", "Madrid, España"),
    RouteSeed("Manzanares, España", "Valencia, España"),
    RouteSeed("Burgos, España", "Madrid, España"),
]


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260330)
    parser.add_argument("--invoices", type=int, default=100)
    parser.add_argument("--routes", type=int, default=50)
    parser.add_argument("--trucks", type=int, default=10)
    return parser.parse_args()


def _chunked[T](items: list[T], size: int) -> list[list[T]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _q2(v: Decimal | float | int) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"))


async def _ensure_empresa(db: SupabaseAsync) -> str:
    res: Any = await db.execute(db.table("empresas").select("id").eq("id", DEMO_EMPRESA_UUID).limit(1))
    rows = (res.data or []) if hasattr(res, "data") else []
    if rows:
        return DEMO_EMPRESA_UUID

    payload = {
        "id": DEMO_EMPRESA_UUID,
        "nombre_comercial": DEMO_EMPRESA_CODE,
        "nombre_legal": "Demo Logistics Sandbox S.L.",
        "nif": DEMO_NIF,
        "plan": "Demo",
    }
    await db.execute(db.table("empresas").insert(payload))
    return DEMO_EMPRESA_UUID


async def _ensure_cliente(db: SupabaseAsync, empresa_id: str) -> str:
    res: Any = await db.execute(
        db.table("clientes")
        .select("id")
        .eq("empresa_id", empresa_id)
        .eq("email", DEMO_CLIENT_EMAIL)
        .limit(1)
    )
    rows = (res.data or []) if hasattr(res, "data") else []
    if rows:
        return str(rows[0]["id"])

    payload = {
        "empresa_id": empresa_id,
        "nombre": "Cliente Demo Retail",
        "nif": "B12345678",
        "email": DEMO_CLIENT_EMAIL,
        "telefono": "+34 600 000 000",
        "direccion": "C/ Demo 100, Madrid",
    }
    ins: Any = await db.execute(db.table("clientes").insert(payload))
    ins_rows = (ins.data or []) if hasattr(ins, "data") else []
    if not ins_rows:
        raise RuntimeError("No se pudo crear cliente demo")
    return str(ins_rows[0]["id"])


async def _seed_flota(db: SupabaseAsync, empresa_id: str, trucks: int) -> list[str]:
    euro_cycle = ["Euro III", "Euro IV", "Euro V", "Euro VI"]
    out_ids: list[str] = []

    for i in range(trucks):
        matricula = f"DEMO{i+1:02d}XYZ"
        q = (
            db.table("flota")
            .select("id")
            .eq("empresa_id", empresa_id)
            .eq("matricula", matricula)
            .limit(1)
        )
        r = await db.execute(q)
        rows = (r.data or []) if hasattr(r, "data") else []
        if rows:
            out_ids.append(str(rows[0]["id"]))
            continue

        normativa = euro_cycle[i % len(euro_cycle)]
        payload = {
            "empresa_id": empresa_id,
            "vehiculo": f"Truck Demo {i+1:02d}",
            "matricula": matricula,
            "precio_compra": float(_q2(70000 + i * 4500)),
            "km_actual": float(_q2(120000 + i * 15500)),
            "estado": "Operativo",
            "tipo_motor": "Diesel",
            "certificacion_emisiones": normativa,
            "normativa_euro": normativa,
            "km_proximo_servicio": float(_q2(150000 + i * 15500)),
            "itv_vencimiento": (date.today() + timedelta(days=120 + i * 8)).isoformat(),
            "seguro_vencimiento": (date.today() + timedelta(days=90 + i * 10)).isoformat(),
        }
        try:
            ins = await db.execute(db.table("flota").insert(payload))
        except Exception:
            # Entornos con check legacy sin Euro III.
            payload["normativa_euro"] = "Euro IV"
            payload["certificacion_emisiones"] = "Euro IV"
            ins = await db.execute(db.table("flota").insert(payload))
        ins_rows = (ins.data or []) if hasattr(ins, "data") else []
        if ins_rows:
            out_ids.append(str(ins_rows[0]["id"]))

    return out_ids


async def _validated_routes(
    *,
    maps: MapsService,
    empresa_id: str,
    count: int,
) -> list[dict[str, Any]]:
    if count > len(ROUTES):
        raise ValueError(f"Se solicitaron {count} rutas y solo hay {len(ROUTES)} seeds")

    valid: list[dict[str, Any]] = []
    for rs in ROUTES[:count]:
        km, mins = await maps.get_distance_and_duration(
            origin=rs.origen,
            destination=rs.destino,
            tenant_empresa_id=empresa_id,
        )
        valid.append(
            {
                "origen": rs.origen,
                "destino": rs.destino,
                "km_estimados": max(1.0, float(_q2(km))),
                "tiempo_estimado_min": int(mins),
            }
        )
    return valid


async def _next_secuencial_and_hash(db: SupabaseAsync, empresa_id: str) -> tuple[int, str]:
    res: Any = await db.execute(
        db.table("facturas")
        .select("numero_secuencial,hash_registro")
        .eq("empresa_id", empresa_id)
        .order("numero_secuencial", desc=True)
        .limit(1)
    )
    rows = (res.data or []) if hasattr(res, "data") else []
    if not rows:
        return 1, GENESIS_HASH
    last_seq = int(rows[0].get("numero_secuencial") or 0)
    last_hash = str(rows[0].get("hash_registro") or "").strip() or GENESIS_HASH
    return last_seq + 1, last_hash


def _build_invoice_rows(
    *,
    empresa_id: str,
    cliente_id: str,
    nif_emisor: str,
    count: int,
    seq_start: int,
    prev_hash: str,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], Decimal]:
    rows: list[dict[str, Any]] = []
    ingresos_base = Decimal("0.00")
    chain_prev = prev_hash

    for i in range(count):
        seq = seq_start + i
        base = _q2(rng.uniform(850, 1850))
        iva = _q2(base * IVA_RATE)
        total = _q2(base + iva)
        fecha = (date.today() - timedelta(days=rng.randint(0, 180))).isoformat()
        num = f"{DEMO_EMPRESA_CODE}-{date.today().year}-{seq:06d}"
        h = generar_hash_factura_oficial(
            VerifactuCadena.HUELLA_EMISION,
            {
                "num_factura": num,
                "fecha_emision": fecha,
                "nif_emisor": nif_emisor,
                "total_factura": float(total),
            },
            chain_prev,
        )
        row = {
            "empresa_id": empresa_id,
            "cliente": cliente_id,
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
            "estado_cobro": "emitida",
        }
        rows.append(row)
        ingresos_base = _q2(ingresos_base + base)
        chain_prev = h

    return rows, ingresos_base


async def _insert_facturas(db: SupabaseAsync, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inserted: list[dict[str, Any]] = []
    for chunk in _chunked(rows, 25):
        res: Any = await db.execute(db.table("facturas").insert(chunk))
        data = (res.data or []) if hasattr(res, "data") else []
        inserted.extend(list(data))
    if len(inserted) != len(rows):
        # Fallback de lectura por numeración demo
        first = rows[0]["num_factura"]
        last = rows[-1]["num_factura"]
        rf: Any = await db.execute(
            db.table("facturas")
            .select("*")
            .eq("empresa_id", rows[0]["empresa_id"])
            .gte("num_factura", first)
            .lte("num_factura", last)
            .order("numero_secuencial")
        )
        fetched = (rf.data or []) if hasattr(rf, "data") else []
        inserted = list(fetched)
    return inserted


async def _seed_portes(
    *,
    db: SupabaseAsync,
    empresa_id: str,
    cliente_id: str,
    vehiculo_ids: list[str],
    routes: list[dict[str, Any]],
    invoice_rows: list[dict[str, Any]],
    rng: random.Random,
) -> int:
    rows: list[dict[str, Any]] = []
    for i, rt in enumerate(routes):
        inv = invoice_rows[i]
        precio = float(inv.get("base_imponible") or 0.0)
        rows.append(
            {
                "empresa_id": empresa_id,
                "cliente_id": cliente_id,
                "fecha": (date.today() - timedelta(days=rng.randint(0, 120))).isoformat(),
                "origen": rt["origen"],
                "destino": rt["destino"],
                "km_estimados": rt["km_estimados"],
                "bultos": 10 + (i % 24),
                "peso_ton": float(_q2(8 + (i % 9) * 0.7)),
                "descripcion": f"Ruta demo validada API ({rt['tiempo_estimado_min']} min)",
                "precio_pactado": precio,
                "vehiculo_id": vehiculo_ids[i % len(vehiculo_ids)] if vehiculo_ids else None,
                "estado": "facturado",
                "factura_id": inv.get("id"),
            }
        )
    inserted = 0
    for chunk in _chunked(rows, 25):
        res: Any = await db.execute(db.table("portes").insert(chunk))
        data = (res.data or []) if hasattr(res, "data") else []
        inserted += len(data)
    return inserted


async def _seed_gastos_for_margin(
    *,
    db: SupabaseAsync,
    empresa_id: str,
    ingresos_base: Decimal,
    margin_target: Decimal,
) -> Decimal:
    target_gastos = _q2(ingresos_base * (Decimal("1.00") - margin_target))
    categories = ["Combustible", "Peajes", "Mantenimiento", "Seguros", "Dietas", "Oficina/Admin"]
    remaining = target_gastos
    rows: list[dict[str, Any]] = []
    for i in range(20):
        if i == 19:
            net = remaining
        else:
            net = _q2(target_gastos / Decimal("20"))
            remaining = _q2(remaining - net)
        iva = _q2(net * Decimal("0.21"))
        total = _q2(net + iva)
        rows.append(
            {
                "empresa_id": empresa_id,
                "empleado": "demo.system@abscanner.local",
                "proveedor": f"Proveedor Demo {i+1:02d}",
                "fecha": (date.today() - timedelta(days=i * 3)).isoformat(),
                "categoria": categories[i % len(categories)],
                "concepto": "Sandbox financiero demo",
                "moneda": "EUR",
                "total_chf": float(total),
                "total_eur": float(total),
                "iva": float(iva),
            }
        )
    for chunk in _chunked(rows, 20):
        await db.execute(db.table("gastos").insert(chunk))
    return target_gastos


async def _seed_bank_transactions(
    *,
    db: SupabaseAsync,
    empresa_id: str,
    invoice_rows: list[dict[str, Any]],
) -> tuple[int, int]:
    rows: list[dict[str, Any]] = []
    for i in range(10):
        inv = invoice_rows[i]
        num = str(inv.get("num_factura") or inv.get("numero_factura") or "")
        total = float(inv.get("total_factura") or 0.0)
        rows.append(
            {
                "empresa_id": empresa_id,
                "transaction_id": f"demo-paid-{date.today().strftime('%Y%m%d')}-{i+1:03d}",
                "amount": total,
                "booked_date": date.today().isoformat(),
                "currency": "EUR",
                "description": f"COBRO FACTURA {num}",
                "reconciled": False,
                "raw_fingerprint": str(uuid4()),
            }
        )
    for i in range(5):
        inv = invoice_rows[10 + i]
        total = float(inv.get("total_factura") or 0.0)
        rows.append(
            {
                "empresa_id": empresa_id,
                "transaction_id": f"demo-pending-{date.today().strftime('%Y%m%d')}-{i+1:03d}",
                "amount": float(_q2(Decimal(str(total)) + Decimal("17.35"))),
                "booked_date": date.today().isoformat(),
                "currency": "EUR",
                "description": f"ABONO PENDIENTE {i+1:02d}",
                "reconciled": False,
                "raw_fingerprint": str(uuid4()),
            }
        )
    for chunk in _chunked(rows, 25):
        await db.execute(db.table("bank_transactions").upsert(chunk, on_conflict="empresa_id,transaction_id"))
    return 10, 5


async def main() -> None:
    args = _args()
    rng = random.Random(args.seed)
    if args.routes > len(ROUTES):
        raise ValueError(f"--routes máximo soportado: {len(ROUTES)}")

    db = await get_supabase(
        jwt_token=None,
        allow_service_role_bypass=True,
        log_service_bypass_warning=False,
    )
    empresa_id = await _ensure_empresa(db)
    try:
        await db.rpc("set_empresa_context", {"p_empresa_id": empresa_id})
    except Exception:
        pass

    cliente_id = await _ensure_cliente(db, empresa_id)
    vehiculo_ids = await _seed_flota(db, empresa_id, args.trucks)

    maps = MapsService(db)
    validated = await _validated_routes(
        maps=maps,
        empresa_id=empresa_id,
        count=args.routes,
    )

    seq_start, prev_hash = await _next_secuencial_and_hash(db, empresa_id)
    invoice_rows_raw, ingresos_base = _build_invoice_rows(
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        nif_emisor=DEMO_NIF,
        count=args.invoices,
        seq_start=seq_start,
        prev_hash=prev_hash,
        rng=rng,
    )
    inserted_invoices = await _insert_facturas(db, invoice_rows_raw)
    inserted_invoices.sort(key=lambda r: int(r.get("numero_secuencial") or 0))

    # Encadenado validado en memoria con las 100 recién insertadas.
    chain_ok = True
    for idx, row in enumerate(inserted_invoices):
        expected_prev = prev_hash if idx == 0 else str(inserted_invoices[idx - 1].get("hash_registro") or "")
        got_prev = str(row.get("hash_anterior") or "")
        if got_prev != expected_prev:
            chain_ok = False
            break

    seeded_routes = await _seed_portes(
        db=db,
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        vehiculo_ids=vehiculo_ids,
        routes=validated,
        invoice_rows=inserted_invoices[: args.routes],
        rng=rng,
    )

    margin_target = Decimal("0.18")
    target_gastos = await _seed_gastos_for_margin(
        db=db,
        empresa_id=empresa_id,
        ingresos_base=ingresos_base,
        margin_target=margin_target,
    )

    paid_tx, pending_tx = await _seed_bank_transactions(
        db=db,
        empresa_id=empresa_id,
        invoice_rows=inserted_invoices,
    )
    recon = ReconciliationService(db)
    reconciled_count, _ = await recon.auto_reconcile_invoices(empresa_id)

    finance = FinanceService(db)
    summary = await finance.financial_summary(empresa_id=empresa_id)
    ingresos = Decimal(str(summary.ingresos))
    ebitda = Decimal(str(summary.ebitda))
    margin = Decimal("0.00")
    if ingresos > 0:
        margin = _q2((ebitda / ingresos) * Decimal("100"))

    print(f"empresa_demo_code={DEMO_EMPRESA_CODE}")
    print(f"empresa_id_used={empresa_id}")
    print(f"fleet_seeded={len(vehiculo_ids)}")
    print(f"routes_seeded={seeded_routes}")
    print(f"invoices_seeded={len(inserted_invoices)}")
    print(f"verifactu_chain_ok={str(chain_ok).lower()}")
    print(f"bank_transactions_paid={paid_tx}")
    print(f"bank_transactions_pending={pending_tx}")
    print(f"reconciled_now={reconciled_count}")
    print(f"ingresos_base_target={float(ingresos_base):.2f}")
    print(f"gastos_target={float(target_gastos):.2f}")
    print(f"ebitda={float(ebitda):.2f}")
    print(f"ebitda_margin_pct={float(margin):.2f}")


if __name__ == "__main__":
    asyncio.run(main())
