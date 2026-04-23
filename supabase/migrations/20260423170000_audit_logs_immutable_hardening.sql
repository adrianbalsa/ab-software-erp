-- =============================================================================
-- Audit Logs Immutable Hardening
-- =============================================================================
-- Objetivo:
-- - Blindar public.audit_logs como append-only a nivel DB.
-- - Bloquear UPDATE/DELETE/TRUNCATE incluso ante grants accidentales.
-- - Mantener compatibilidad con inserciones existentes (triggers y service_role).
-- =============================================================================

BEGIN;

-- 1) RLS activa (defensa en profundidad)
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- 2) Revocar mutaciones explícitamente (incluye TRUNCATE)
REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_logs FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_logs FROM authenticated;
REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_logs FROM anon;
REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_logs FROM service_role;

-- 3) Trigger de bloqueo duro para UPDATE/DELETE
CREATE OR REPLACE FUNCTION public.audit_logs_block_row_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'audit_logs es append-only: % no permitido', TG_OP
    USING ERRCODE = '42501';
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_logs_block_update_delete ON public.audit_logs;
CREATE TRIGGER trg_audit_logs_block_update_delete
  BEFORE UPDATE OR DELETE ON public.audit_logs
  FOR EACH ROW
  EXECUTE PROCEDURE public.audit_logs_block_row_mutation();

-- 4) Trigger de bloqueo para TRUNCATE
CREATE OR REPLACE FUNCTION public.audit_logs_block_truncate()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'audit_logs es append-only: TRUNCATE no permitido'
    USING ERRCODE = '42501';
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_logs_block_truncate ON public.audit_logs;
CREATE TRIGGER trg_audit_logs_block_truncate
  BEFORE TRUNCATE ON public.audit_logs
  FOR EACH STATEMENT
  EXECUTE PROCEDURE public.audit_logs_block_truncate();

COMMENT ON FUNCTION public.audit_logs_block_row_mutation IS
  'Bloquea UPDATE/DELETE sobre public.audit_logs (append-only).';
COMMENT ON FUNCTION public.audit_logs_block_truncate IS
  'Bloquea TRUNCATE sobre public.audit_logs (append-only).';

COMMIT;
