from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any, Iterable


# Permite `import app.*` apuntando al paquete backend/
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings
from app.core.crypto import PiiCrypto


def _looks_like_fernet_token(value: Any) -> bool:
    """
    Pista estándar Fernet: tokens base64 url-safe suelen empezar por `gAAAA`.
    """
    if value is None:
        return False
    if not isinstance(value, str):
        value = str(value)
    s = value.strip()
    return s.startswith("gAAAA") and len(s) > 10


@dataclass(frozen=True, slots=True)
class TablePlan:
    table: str
    pk_col: str
    columns: list[str]


TABLES_PII: list[TablePlan] = [
    TablePlan(table="empresas", pk_col="id", columns=["nif", "iban"]),
    TablePlan(table="clientes", pk_col="id", columns=["nif"]),
    TablePlan(table="facturas", pk_col="id", columns=["nif_emisor", "nif_cliente", "nif_empresa"]),
    TablePlan(table="gastos", pk_col="id", columns=["nif_proveedor"]),
    TablePlan(table="presupuestos", pk_col="id", columns=["nif_empresa", "nif_cliente"]),
]


def _chunked(items: list[Any], chunk_size: int) -> Iterable[list[Any]]:
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def _safe_encrypt(crypto: PiiCrypto, value: Any) -> str:
    # Normalizamos a string antes de cifrar; Fernet devuelve token ASCII.
    s = str(value).strip()
    return crypto.encrypt_pii(s) or ""


def _validate_key_present() -> None:
    key = os.getenv("PII_ENCRYPTION_KEY")
    if key is None or not str(key).strip():
        raise RuntimeError("Missing env var `PII_ENCRYPTION_KEY` (required for re-encryption).")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Re-encrypt legacy PII values using Fernet.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula el proceso y NO escribe en la base de datos.",
    )
    p.add_argument(
        "--chunk-size",
        type=int,
        default=200,
        help="Tamaño de chunk para minimizar escrituras/llamadas (default: 200).",
    )
    return p.parse_args()


def _get_supabase_client():
    # Import tardío para no obligar a side-effects si no hace falta
    from supabase import create_client

    s = get_settings()
    return create_client(s.SUPABASE_URL, s.SUPABASE_SERVICE_KEY)


def _get_database_url() -> str | None:
    s = get_settings()
    return s.DATABASE_URL


def _reencrypt_chunk_sql(
    conn: Any,
    *,
    plan: TablePlan,
    rows_to_update: list[dict[str, Any]],
    chunk_cols: list[str],
) -> None:
    """
    Ejecuta UPDATE por chunk:
      - usa CASE por columna
      - actualiza solo claves del chunk (WHERE pk IN ...)
    """
    from psycopg.sql import Identifier, SQL

    pk = plan.pk_col
    pk_values = [r[pk] for r in rows_to_update]

    set_parts: list[SQL] = []
    params: list[Any] = []

    for col in chunk_cols:
        # CASE solo con filas que realmente necesitan este campo.
        cases: list[str] = []
        case_params: list[Any] = []
        for row in rows_to_update:
            if col not in row["__updates__"]:
                continue
            cases.append("WHEN %s THEN %s")
            case_params.extend([row[pk], row["__updates__"][col]])

        if not cases:
            continue

        case_sql = SQL("CASE {} {} ELSE {} END").format(
            Identifier(pk),
            SQL(" ".join(cases)),
            Identifier(col),
        )
        set_parts.append(SQL("{} = {}").format(Identifier(col), case_sql))
        params.extend(case_params)

    if not set_parts:
        return

    where_placeholders = ", ".join(["%s"] * len(pk_values))
    query = SQL("UPDATE public.{} SET {} WHERE {} IN ({})").format(
        Identifier(plan.table),
        SQL(", ").join(set_parts),
        Identifier(pk),
        SQL(where_placeholders),
    )
    params.extend(pk_values)
    with conn.cursor() as cur:
        cur.execute(query, params)


def main() -> None:
    args = parse_args()
    _validate_key_present()
    crypto = PiiCrypto()

    database_url = _get_database_url()
    use_sql = bool(database_url and str(database_url).strip())

    print(f"[reencrypt_legacy_data] dry-run={args.dry_run} chunk_size={args.chunk_size} use_sql={use_sql}")

    per_table_blindados: dict[str, int] = {}

    if use_sql:
        import psycopg

        conn = psycopg.connect(database_url)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                _ = cur.fetchone()
        except Exception as exc:
            conn.close()
            raise RuntimeError(f"Database connection test failed: {exc}") from exc

        plans = TABLES_PII
        for plan in plans:
            print(f"\n[table={plan.table}] columns={plan.columns} pk={plan.pk_col}")

            blindados_rows = 0

            select_cols = ", ".join([plan.pk_col] + plan.columns)
            query = f"SELECT {select_cols} FROM public.{plan.table};"

            # Cursor streaming por servidor (evita cargar toda la tabla en RAM)
            with conn.cursor(name=f"reencrypt_{plan.table}") as cur:
                cur.itersize = args.chunk_size
                cur.execute(query)

                while True:
                    batch = cur.fetchmany(args.chunk_size)
                    if not batch:
                        break

                    rows_to_update: list[dict[str, Any]] = []

                    for row in batch:
                        row_map: dict[str, Any] = dict(zip([plan.pk_col] + plan.columns, row))
                        pk_val = row_map.get(plan.pk_col)
                        if pk_val is None:
                            continue

                        updates: dict[str, Any] = {}
                        any_need = False
                        for col in plan.columns:
                            cur_val = row_map.get(col)
                            if cur_val is None:
                                continue
                            if not isinstance(cur_val, str):
                                cur_val = str(cur_val)
                            if not cur_val.strip():
                                continue

                            if _looks_like_fernet_token(cur_val):
                                # Ya cifrado (o al menos parece token) -> no tocar.
                                continue

                            any_need = True
                            updates[col] = _safe_encrypt(crypto, cur_val)

                        if any_need:
                            blindados_rows += 1
                            rows_to_update.append({plan.pk_col: pk_val, "__updates__": updates})

                    if not rows_to_update or args.dry_run:
                        continue

                    # Actualización en lote por chunk
                    # (si batch_to_update se excede, se reaplica chunk_size)
                    for chunk in _chunked(rows_to_update, args.chunk_size):
                        _reencrypt_chunk_sql(
                            conn,
                            plan=plan,
                            rows_to_update=chunk,
                            chunk_cols=plan.columns,
                        )
            per_table_blindados[plan.table] = blindados_rows
            print(f"[table={plan.table}] blindados_rows={blindados_rows}")

        conn.close()
        print("\n[summary]")
        for table, n in per_table_blindados.items():
            print(f" - {table}: {n} filas blindadas")
        return

    # Fallback: sin DATABASE_URL -> supabase-py para SELECT/UPDATE (upsert por chunk).
    supabase = _get_supabase_client()

    for plan in TABLES_PII:
        print(f"\n[table={plan.table}] columns={plan.columns} pk={plan.pk_col}")

        blindados_rows = 0
        offset = 0

        select_cols = ", ".join([plan.pk_col] + plan.columns)
        while True:
            res = (
                supabase.table(plan.table)
                .select(select_cols)
                .order(plan.pk_col)
                .range(offset, offset + args.chunk_size - 1)
                .execute()
            )
            rows = res.data or []
            if not rows:
                break

            records_to_upsert: list[dict[str, Any]] = []

            for r in rows:
                pk_val = r.get(plan.pk_col)
                if pk_val is None:
                    continue
                updates: dict[str, Any] = {}
                needs_any = False

                # Construimos fila completa para evitar nulos en upsert.
                new_row: dict[str, Any] = {plan.pk_col: pk_val}

                for col in plan.columns:
                    cur_val = r.get(col)
                    new_val = cur_val
                    if cur_val is None:
                        new_row[col] = None
                        continue
                    cur_s = str(cur_val).strip()
                    if cur_s == "":
                        new_row[col] = cur_val
                        continue
                    if _looks_like_fernet_token(cur_s):
                        new_val = cur_s
                    else:
                        new_val = _safe_encrypt(crypto, cur_s)
                        updates[col] = new_val
                        needs_any = True
                    new_row[col] = new_val

                if needs_any:
                    blindados_rows += 1
                    records_to_upsert.append(new_row)

            if records_to_upsert and not args.dry_run:
                for chunk in _chunked(records_to_upsert, args.chunk_size):
                    supabase.table(plan.table).upsert(chunk, on_conflict=plan.pk_col).execute()

            offset += args.chunk_size

        per_table_blindados[plan.table] = blindados_rows
        print(f"[table={plan.table}] blindados_rows={blindados_rows}")

    print("\n[summary]")
    for table, n in per_table_blindados.items():
        print(f" - {table}: {n} filas blindadas")


if __name__ == "__main__":
    main()

