#!/usr/bin/env python3
"""
Re-cálculo de huellas VeriFactu persistidas (``huella_hash`` / ``hash_registro`` / ``hash_factura``)
con :class:`app.core.verifactu_hashing.CanonicalHashService`.

**Requisitos**
- ``DATABASE_URL`` (Postgres con permiso ``ALTER TABLE ... DISABLE TRIGGER`` sobre ``public.facturas``).
- Secret Manager / env para ``get_verifactu_genesis_hash_for_issuer`` (misma fuente que emisión).

**Inmutabilidad**
Dentro de una única transacción se desactivan los triggers de inmutabilidad en ``facturas``, se aplican
los ``UPDATE`` y se reactivan los triggers antes del ``COMMIT`` (si algo falla, el ``ROLLBACK``
restaura también el estado de los triggers).

**Cadena**
Por ``empresa_id``, facturas con ``bloqueado = true`` ordenadas por ``numero_secuencial`` ASC, ``id`` ASC.
La primera usa como huella anterior el **génesis** del emisor; cada siguiente usa la huella recién
calculada de la anterior. Si el despliegue encadena **por serie**, adapte la consulta antes de ``--apply``.

Uso (desde ``backend/``)::

  python scripts/normalize_historical_hashes.py --dry-run
  python scripts/normalize_historical_hashes.py --apply --empresa-id <uuid>
"""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

_ENV_FILE = BACKEND_ROOT.parent / ".env"
if _ENV_FILE.exists():
    try:
        from dotenv import dotenv_values

        for k, v in dotenv_values(_ENV_FILE).items():
            if k and v is not None and not os.getenv(k):
                os.environ[k] = str(v)
    except ImportError:
        pass

from sqlalchemy import text

from app.core.crypto import pii_crypto
from app.core.verifactu_hashing import CanonicalHashService
from app.db.session import get_engine
from app.services.verifactu_genesis import get_verifactu_genesis_hash_for_issuer


def _disable_factura_triggers(conn: Any) -> None:
    conn.execute(
        text("ALTER TABLE public.facturas DISABLE TRIGGER trg_facturas_immutable_hash")
    )
    conn.execute(
        text(
            """
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM pg_trigger t
                JOIN pg_class c ON c.oid = t.tgrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = 'facturas'
                  AND NOT t.tgisinternal AND t.tgname = 'trg_verifactu_immutable'
              ) THEN
                EXECUTE 'ALTER TABLE public.facturas DISABLE TRIGGER trg_verifactu_immutable';
              END IF;
            END $$;
            """
        )
    )


def _enable_factura_triggers(conn: Any) -> None:
    conn.execute(
        text("ALTER TABLE public.facturas ENABLE TRIGGER trg_facturas_immutable_hash")
    )
    conn.execute(
        text(
            """
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM pg_trigger t
                JOIN pg_class c ON c.oid = t.tgrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = 'facturas'
                  AND NOT t.tgisinternal AND t.tgname = 'trg_verifactu_immutable'
              ) THEN
                EXECUTE 'ALTER TABLE public.facturas ENABLE TRIGGER trg_verifactu_immutable';
              END IF;
            END $$;
            """
        )
    )


def _rows_for_empresa(conn: Any, empresa_id: str, limit: int | None) -> list[dict[str, Any]]:
    lim_sql = f"LIMIT {int(limit)}" if limit else ""
    res = conn.execute(
        text(
            f"""
            SELECT id, empresa_id, num_factura, numero_factura, fecha_emision, total_factura,
                   nif_emisor, bloqueado, numero_secuencial
            FROM public.facturas
            WHERE empresa_id = CAST(:eid AS uuid)
              AND bloqueado IS TRUE
            ORDER BY numero_secuencial ASC NULLS LAST, id ASC
            {lim_sql}
            """
        ),
        {"eid": empresa_id},
    )
    return [dict(r) for r in res.mappings().all()]


def _empresa_ids(conn: Any) -> list[str]:
    res = conn.execute(
        text(
            """
            SELECT DISTINCT empresa_id::text AS eid
            FROM public.facturas
            WHERE bloqueado IS TRUE
            ORDER BY 1
            """
        )
    )
    return [str(r[0]) for r in res.fetchall() if r[0]]


def main() -> int:
    parser = argparse.ArgumentParser(description="Normaliza huellas VeriFactu con CanonicalHashService")
    parser.add_argument("--dry-run", action="store_true", help="Solo listar diferencias")
    parser.add_argument("--apply", action="store_true", help="Persistir UPDATE en la misma transacción")
    parser.add_argument("--empresa-id", type=str, default="", help="Limitar a una empresa (uuid)")
    parser.add_argument("--limit", type=int, default=None, help="Máximo de facturas por empresa")
    args = parser.parse_args()
    apply = bool(args.apply)
    dry_run = bool(args.dry_run) or not apply

    eng = get_engine()
    if eng is None:
        print("ERROR: DATABASE_URL no configurada.", file=sys.stderr)
        return 1

    with eng.begin() as conn:
        _disable_factura_triggers(conn)
        try:
            eids = [args.empresa_id.strip()] if args.empresa_id.strip() else _empresa_ids(conn)
            if not eids:
                print("No hay facturas bloqueadas.")
                return 0

            total_considered = 0
            total_updated = 0
            for eid in eids:
                rows = _rows_for_empresa(conn, eid, args.limit)
                if not rows:
                    continue
                first = rows[0]
                raw_nif = str(first.get("nif_emisor") or "").strip()
                nif_plain = pii_crypto.decrypt_pii(raw_nif) or raw_nif
                prev_hash = get_verifactu_genesis_hash_for_issuer(
                    issuer_id=str(eid),
                    issuer_nif=nif_plain,
                )
                total_considered += len(rows)
                for row in rows:
                    rid = int(row["id"])
                    raw_ne = str(row.get("nif_emisor") or "").strip()
                    nif_e = pii_crypto.decrypt_pii(raw_ne) or raw_ne
                    num = str(row.get("num_factura") or row.get("numero_factura") or "").strip()
                    raw_fe = row.get("fecha_emision")
                    if hasattr(raw_fe, "isoformat"):
                        try:
                            fecha = raw_fe.isoformat()[:10]
                        except Exception:
                            fecha = str(raw_fe)[:10]
                    else:
                        fecha = str(raw_fe or "")[:10]
                    tot_raw = row.get("total_factura")
                    tot = tot_raw if isinstance(tot_raw, Decimal) else Decimal(str(tot_raw or 0))

                    huella_prev = prev_hash
                    new_h = CanonicalHashService.generate_verifactu_hash(
                        nif_emisor=nif_e,
                        num_serie_factura=num,
                        fecha_expedicion=fecha,
                        importe_total=tot,
                        huella_anterior=huella_prev,
                    )

                    cur = (
                        conn.execute(
                            text(
                                """
                                SELECT trim(COALESCE(huella_hash, hash_registro, hash_factura, '')::text) AS h
                                FROM public.facturas WHERE id = :id
                                """
                            ),
                            {"id": rid},
                        )
                        .mappings()
                        .first()
                    )
                    old_h = str((cur or {}).get("h") or "")
                    if old_h.upper() != new_h.upper():
                        total_updated += 1
                        print(f"empresa={eid} id={rid} old={old_h[:16]}… new={new_h[:16]}…")
                    if apply:
                        conn.execute(
                            text(
                                """
                                UPDATE public.facturas
                                SET huella_hash = CAST(:nh AS text),
                                    hash_registro = CAST(:nh AS text),
                                    hash_factura = CAST(:nh AS text),
                                    huella_anterior = CAST(:hp AS text),
                                    hash_anterior = CAST(:hp AS text)
                                WHERE id = :id AND empresa_id = CAST(:eid AS uuid)
                                """
                            ),
                            {"nh": new_h, "hp": huella_prev, "id": rid, "eid": eid},
                        )
                    prev_hash = new_h

            print(
                f"Resumen: consideradas={total_considered} "
                f"diferentes={total_updated} dry_run={dry_run} apply={apply}"
            )
            if dry_run and apply:
                print("ADVERTENCIA: --apply y --dry-run juntos; se aplicó por --apply.", file=sys.stderr)
        finally:
            _enable_factura_triggers(conn)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
