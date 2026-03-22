#!/usr/bin/env python3
"""
Stress test: concurrencia sobre POST /facturas/desde-portes.

Requisitos:
  - API en marcha (p. ej. uvicorn) y base de datos con datos válidos por tenant.
  - Por cada worker: JWT + cliente_id con portes en estado ``pendiente`` para esa empresa.

Variables de entorno (ver también ``backend/.env``):
  STRESS_API_URL          URL base (default: http://127.0.0.1:8000)
  STRESS_CONCURRENCY      Peticiones simultáneas (default: 50)
  STRESS_CONFIG_PATH      JSON con lista de {token, cliente_id, empresa_id?}
  STRESS_TIMEOUT_S        Timeout HTTP por petición (default: 120)
  SUPABASE_URL + SUPABASE_SERVICE_KEY  Opcional: verificación de cadena VeriFactu vía REST

Uso (desde ``backend/``):
  python tests/stress_test_load.py
  STRESS_CONFIG_PATH=tests/stress_config.json STRESS_CONCURRENCY=50 python tests/stress_test_load.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Carga .env antes de importar app (verificación VeriFactu)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if _BACKEND_ROOT.name == "backend":
    try:
        from dotenv import load_dotenv

        load_dotenv(_BACKEND_ROOT / ".env")
    except ImportError:
        pass

import httpx


@dataclass
class WorkerConfig:
    token: str
    cliente_id: str
    empresa_id: str | None = None


@dataclass
class RequestOutcome:
    ok: bool
    latency_s: float
    status_code: int | None = None
    error: str | None = None
    empresa_id: str | None = None
    hash_registro: str | None = None


@dataclass
class StressSummary:
    outcomes: list[RequestOutcome] = field(default_factory=list)
    wall_time_s: float = 0.0


def _load_config(path: Path) -> list[WorkerConfig]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("El JSON debe ser un array de objetos {token, cliente_id, empresa_id?}")
    out: list[WorkerConfig] = []
    for i, row in enumerate(raw):
        if not isinstance(row, dict):
            raise ValueError(f"Entrada {i} no es un objeto")
        tok = str(row.get("token") or "").strip()
        cid = str(row.get("cliente_id") or "").strip()
        eid = row.get("empresa_id")
        eid_s = str(eid).strip() if eid else None
        if not tok or not cid:
            raise ValueError(f"Entrada {i}: token y cliente_id son obligatorios")
        out.append(WorkerConfig(token=tok, cliente_id=cid, empresa_id=eid_s))
    return out


def _decode_empresa_from_jwt(token: str) -> str | None:
    try:
        from jose import jwt as jose_jwt

        secret = os.getenv("JWT_SECRET_KEY") or ""
        if not secret:
            return None
        payload = jose_jwt.decode(
            token,
            secret,
            algorithms=[os.getenv("JWT_ALGORITHM") or "HS256"],
            options={"verify_aud": False},
        )
        e = payload.get("empresa_id")
        return str(e).strip() if e else None
    except Exception:
        return None


async def _one_request(
    client: httpx.AsyncClient,
    base_url: str,
    wc: WorkerConfig,
    timeout_s: float,
) -> RequestOutcome:
    url = f"{base_url.rstrip('/')}/facturas/desde-portes"
    headers = {
        "Authorization": f"Bearer {wc.token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {"cliente_id": wc.cliente_id, "iva_porcentaje": 21.0}
    t0 = time.perf_counter()
    try:
        r = await client.post(url, json=body, headers=headers, timeout=timeout_s)
        dt = time.perf_counter() - t0
        if r.status_code != 201:
            return RequestOutcome(
                ok=False,
                latency_s=dt,
                status_code=r.status_code,
                error=r.text[:500],
            )
        data = r.json()
        fact = data.get("factura") or {}
        h = fact.get("hash_registro") or fact.get("hash_factura")
        eid = None
        if wc.empresa_id:
            eid = wc.empresa_id
        else:
            fe = fact.get("empresa_id")
            if fe:
                eid = str(fe)
            else:
                eid = _decode_empresa_from_jwt(wc.token)
        return RequestOutcome(
            ok=True,
            latency_s=dt,
            status_code=201,
            empresa_id=eid,
            hash_registro=str(h) if h else None,
        )
    except httpx.TimeoutException as e:
        dt = time.perf_counter() - t0
        return RequestOutcome(ok=False, latency_s=dt, error=f"timeout: {e}")
    except Exception as e:
        dt = time.perf_counter() - t0
        return RequestOutcome(ok=False, latency_s=dt, error=str(e)[:500])


async def run_stress(
    *,
    base_url: str,
    workers: list[WorkerConfig],
    concurrency: int,
    timeout_s: float,
) -> StressSummary:
    """Lanza ``concurrency`` peticiones; repite workers con índice i % len(workers) si hace falta."""
    if not workers:
        raise ValueError("No hay workers en la configuración")
    tasks: list[asyncio.Task[RequestOutcome]] = []
    t_wall0 = time.perf_counter()
    async with httpx.AsyncClient() as client:
        for i in range(concurrency):
            wc = workers[i % len(workers)]
            tasks.append(
                asyncio.create_task(_one_request(client, base_url, wc, timeout_s))
            )
        outcomes = await asyncio.gather(*tasks)
    wall = time.perf_counter() - t_wall0
    return StressSummary(outcomes=list(outcomes), wall_time_s=wall)


def _print_metrics(summary: StressSummary, concurrency: int) -> None:
    latencies = [o.latency_s for o in summary.outcomes]
    oks = [o for o in summary.outcomes if o.ok]
    fails = [o for o in summary.outcomes if not o.ok]

    if not latencies:
        print("Sin resultados.")
        return

    lat_ms = [x * 1000 for x in latencies]
    rps = concurrency / summary.wall_time_s if summary.wall_time_s > 0 else 0.0
    success_rate = (len(oks) / len(summary.outcomes)) * 100.0 if summary.outcomes else 0.0

    print()
    print("=" * 64)
    print(" STRESS TEST — POST /facturas/desde-portes")
    print("=" * 64)
    print(f"{'Workers concurrentes:':<28} {concurrency}")
    print(f"{'Peticiones totales:':<28} {len(summary.outcomes)}")
    print(f"{'Tiempo total (wall):':<28} {summary.wall_time_s:.3f} s")
    print(f"{'Throughput (RPS):':<28} {rps:.2f}")
    print(f"{'Tasa de éxito (HTTP 201):':<28} {success_rate:.1f}% ({len(oks)}/{len(summary.outcomes)})")
    print()
    print("--- Latencia (segundos) ---")
    print(f"{'Min:':<12} {min(latencies):.4f}  ({min(lat_ms):.1f} ms)")
    print(f"{'Max:':<12} {max(latencies):.4f}  ({max(lat_ms):.1f} ms)")
    print(f"{'Media:':<12} {statistics.mean(latencies):.4f}  ({statistics.mean(lat_ms):.1f} ms)")
    if len(latencies) > 1:
        print(f"{'Mediana:':<12} {statistics.median(latencies):.4f}  ({statistics.median(lat_ms):.1f} ms)")
    print()
    print("--- Resumen JSON + hash (éxitos) ---")
    with_hash = sum(1 for o in oks if o.hash_registro)
    print(f"Respuestas con hash_registro en JSON: {with_hash}/{len(oks)}")
    if fails:
        print()
        print("--- Fallos (muestra hasta 8) ---")
        for o in fails[:8]:
            detail = o.error or f"HTTP {o.status_code}"
            print(f"  status={o.status_code}  {detail[:120]}")
    print("=" * 64)


def _verify_verifactu_chain(
    *,
    empresa_ids: set[str],
    supabase_url: str,
    service_key: str,
) -> tuple[bool, list[str]]:
    """
    Comprueba por empresa:
      1) Cada fila: hash_registro == generar_hash_factura(..., hash_anterior de la fila).
      2) Encadenamiento: hash_anterior[i] == hash_registro[i-1] (i>=1).
    """
    sys.path.insert(0, str(_BACKEND_ROOT))
    from app.services.verifactu_service import VerifactuService

    errors: list[str] = []
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Accept": "application/json",
    }

    for eid in sorted(empresa_ids):
        if not eid:
            continue
        with httpx.Client(timeout=60.0) as client:
            r = client.get(
                f"{supabase_url.rstrip('/')}/rest/v1/facturas",
                params={
                    "empresa_id": f"eq.{eid}",
                    "select": "*",
                    "order": "numero_secuencial.asc",
                },
                headers=headers,
            )
            if r.status_code != 200:
                errors.append(f"[{eid}] REST facturas HTTP {r.status_code}: {r.text[:200]}")
                continue
            rows = r.json()
            if not isinstance(rows, list):
                errors.append(f"[{eid}] respuesta inesperada")
                continue

            # NIFs cliente
            cids = list(
                dict.fromkeys(str(x.get("cliente") or "").strip() for x in rows if x.get("cliente"))
            )
            nif_map: dict[str, str] = {}
            if cids:
                in_list = ",".join(cids)
                r2 = client.get(
                    f"{supabase_url.rstrip('/')}/rest/v1/clientes",
                    params={
                        "id": f"in.({in_list})",
                        "select": "id,nif",
                        "empresa_id": f"eq.{eid}",
                    },
                    headers=headers,
                )
                if r2.status_code == 200 and isinstance(r2.json(), list):
                    for cr in r2.json():
                        nif_map[str(cr.get("id"))] = str(cr.get("nif") or "").strip()

            for i, row in enumerate(rows):
                cid = str(row.get("cliente") or "").strip()
                nif_c = nif_map.get(cid, "")
                nif_e = str(row.get("nif_emisor") or "").strip()
                num = str(row.get("num_factura") or row.get("numero_factura") or "").strip()
                fe = row.get("fecha_emision")
                fecha = str(fe)[:10] if fe else ""
                try:
                    tot = float(row.get("total_factura") or 0.0)
                except (TypeError, ValueError):
                    tot = 0.0
                h_prev_col = row.get("hash_anterior")
                h_prev = str(h_prev_col).strip() if h_prev_col else None
                if h_prev == "":
                    h_prev = None
                tipo = str(row.get("tipo_factura") or "").strip() or None
                rect = row.get("factura_rectificada_id")
                num_rect = None
                if tipo and tipo.upper() == "R1" and rect is not None:
                    # Buscar número de la F1 rectificada
                    r3 = client.get(
                        f"{supabase_url.rstrip('/')}/rest/v1/facturas",
                        params={
                            "id": f"eq.{rect}",
                            "select": "num_factura,numero_factura",
                            "empresa_id": f"eq.{eid}",
                        },
                        headers=headers,
                    )
                    if r3.status_code == 200 and r3.json():
                        orig = r3.json()[0]
                        num_rect = str(orig.get("num_factura") or orig.get("numero_factura") or "")

                expected = VerifactuService.generar_hash_factura(
                    nif_empresa=nif_e,
                    nif_cliente=nif_c,
                    num_factura=num,
                    fecha=fecha,
                    total=tot,
                    hash_anterior=h_prev,
                    tipo_factura=tipo,
                    num_factura_rectificada=num_rect,
                )
                got = str(row.get("hash_registro") or row.get("hash_factura") or "").strip()
                if got and expected != got:
                    errors.append(
                        f"[{eid}] id={row.get('id')} hash_registro no coincide con cadena canónica"
                    )

                if i > 0:
                    prev = rows[i - 1]
                    prev_h = str(prev.get("hash_registro") or prev.get("hash_factura") or "").strip()
                    cur_ha = h_prev or ""
                    if prev_h and cur_ha and prev_h != cur_ha:
                        errors.append(
                            f"[{eid}] encadenamiento roto entre seq "
                            f"{prev.get('numero_secuencial')} -> {row.get('numero_secuencial')}"
                        )

    return (len(errors) == 0, errors)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stress test POST /facturas/desde-portes")
    parser.add_argument(
        "--config",
        default=os.getenv("STRESS_CONFIG_PATH", str(_BACKEND_ROOT / "tests" / "stress_config.json")),
        help="JSON con lista de {token, cliente_id, empresa_id?}",
    )
    parser.add_argument("--url", default=os.getenv("STRESS_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("STRESS_CONCURRENCY", "50")),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("STRESS_TIMEOUT_S", "120")),
    )
    parser.add_argument("--skip-integrity", action="store_true", help="No verificar cadena VeriFactu")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.is_file():
        print(
            f"ERROR: No existe el fichero de configuración: {cfg_path}\n"
            f"Copia tests/stress_config.example.json a stress_config.json y rellena tokens/clientes.",
            file=sys.stderr,
        )
        return 2

    workers = _load_config(cfg_path)
    conc = max(1, args.concurrency)
    if conc > len(workers):
        print(
            f"AVISO: STRESS_CONCURRENCY={conc} > {len(workers)} entradas en config; "
            f"se reutilizarán tenants con workers[i % {len(workers)}].",
            file=sys.stderr,
        )

    summary = asyncio.run(
        run_stress(
            base_url=args.url,
            workers=workers,
            concurrency=conc,
            timeout_s=args.timeout,
        )
    )
    _print_metrics(summary, conc)

    if args.skip_integrity:
        return 0 if all(o.ok for o in summary.outcomes) else 1

    supabase_url = (os.getenv("SUPABASE_URL") or "").strip()
    service_key = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    if not supabase_url or not service_key:
        print()
        print("Integridad VeriFactu: OMITIDA (defina SUPABASE_URL y SUPABASE_SERVICE_KEY).")
        return 0 if all(o.ok for o in summary.outcomes) else 1

    empresa_ids: set[str] = set()
    for o in summary.outcomes:
        if o.ok and o.empresa_id:
            empresa_ids.add(o.empresa_id)

    if not empresa_ids:
        print()
        print("Integridad VeriFactu: OMITIDA (ningún éxito con empresa_id identificable).")
        return 0 if all(o.ok for o in summary.outcomes) else 1

    print()
    print("--- Integridad cadena VeriFactu (PostgREST + service role) ---")
    ok_chain, errs = _verify_verifactu_chain(
        empresa_ids=empresa_ids,
        supabase_url=supabase_url,
        service_key=service_key,
    )
    if ok_chain:
        print(f"OK: cadena coherente para {len(empresa_ids)} empresa(s) analizada(s).")
    else:
        print(f"FALLO: {len(errs)} problema(s):")
        for e in errs[:20]:
            print(f"  - {e}")
        if len(errs) > 20:
            print(f"  ... y {len(errs) - 20} más")
        return 1

    return 0 if all(o.ok for o in summary.outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
