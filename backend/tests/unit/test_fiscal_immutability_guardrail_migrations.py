"""
Repo-level guardrail: migraciones Supabase contienen triggers de inmutabilidad fiscal esperados.

No sustituye el smoke SQL contra Postgres (`scripts/verify_fiscal_immutability_smoke.sql`), pero sí da
evidencia reproducible en CI sin base de datos.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _read(rel: str) -> str:
    return (_REPO_ROOT / rel).read_text(encoding="utf-8")


def _strip_sql_line_comments(sql: str) -> str:
    """Elimina líneas/comentarios finales ``--`` para asserts sobre código (no texto en comentarios)."""
    out: list[str] = []
    for raw in sql.splitlines():
        line = raw
        if "--" in line:
            line = line.split("--", 1)[0]
        out.append(line)
    return "\n".join(out)


def test_migration_facturas_final_seal_has_strict_and_truncate_triggers() -> None:
    sql = _read("supabase/migrations/20260428184500_facturas_immutability_final_seal.sql")
    assert "CREATE OR REPLACE FUNCTION public.enforce_immutable_facturas_strict()" in sql
    assert "trg_facturas_immutable_hash" in sql
    assert "CREATE OR REPLACE FUNCTION public.prevent_truncate_immutable()" in sql
    assert "trg_facturas_prevent_truncate_immutable" in sql


def test_migration_compliance_guardrail_replaces_legacy_service_role_bypass() -> None:
    sql = _read("supabase/migrations/20260429090000_compliance_final_guardrail.sql")
    assert "enforce_immutable_facturas_strict()" in sql
    assert "enforce_immutable_auditoria_strict()" in sql
    assert "enforce_immutable_when_hashed()" in sql
    body = _strip_sql_line_comments(sql)
    assert "current_setting('role'" not in body


def test_migration_audit_logs_append_only_triggers() -> None:
    sql = _read("supabase/migrations/20260423170000_audit_logs_immutable_hardening.sql")
    assert "trg_audit_logs_block_update_delete" in sql
    assert "trg_audit_logs_block_truncate" in sql
