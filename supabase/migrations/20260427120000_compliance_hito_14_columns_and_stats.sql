-- Hito 1.4 OPS: columnas de transición Argon2id / trazabilidad PII y estadísticas agregadas (sin PII).
-- RLS: las políticas existentes filan por fila; nuevas columnas no alteran USING/WITH CHECK salvo que referencien columnas nuevas (no es el caso).

BEGIN;

-- 1) usuarios.needs_rehash — true si hash aún es SHA-256 legacy (64 hex); false si Argon2id u otro.
ALTER TABLE public.usuarios
  ADD COLUMN IF NOT EXISTS needs_rehash boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.usuarios.needs_rehash IS
  'True: hash de contraseña pendiente de normalizar a Argon2id (p. ej. legacy SHA-256 hex). False: Argon2id u operativo.';

UPDATE public.usuarios
SET needs_rehash = true
WHERE password_hash ~ '^[a-fA-F0-9]{64}$';

UPDATE public.usuarios
SET needs_rehash = false
WHERE password_hash LIKE '$argon2id$%';

CREATE INDEX IF NOT EXISTS idx_usuarios_needs_rehash
  ON public.usuarios (needs_rehash)
  WHERE needs_rehash IS TRUE;

-- 2) clientes.pseudonymized_at — marcas de backfill permitidas (tabla mutable).
ALTER TABLE public.clientes
  ADD COLUMN IF NOT EXISTS pseudonymized_at timestamptz;

COMMENT ON COLUMN public.clientes.pseudonymized_at IS
  'Marca temporal de proceso de cumplimiento/pseudonimización de PII (backfill operativo); no sustituye RLS.';

CREATE INDEX IF NOT EXISTS idx_clientes_pseudonymized_at_null
  ON public.clientes (id)
  WHERE pseudonymized_at IS NULL;

-- 3) audit_logs: append-only. Columna generada = created_at materializado.
-- IMPORTANTE: ADD ... GENERATED ... STORED reescribe el heap y en PG dispara UPDATE por fila;
-- la migracion 20260423170000 instala BEFORE UPDATE que bloquea cualquier UPDATE → hay que
-- desactivar ese trigger solo durante el ALTER (no debilita RLS ni el modelo append-only).
DO $audit_pseudo$
DECLARE
  has_blocker boolean := false;
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'audit_logs'
      AND column_name = 'pseudonymized_at'
  ) THEN
    RETURN;
  END IF;

  SELECT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_trigger t
    JOIN pg_catalog.pg_class c ON c.oid = t.tgrelid
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = 'audit_logs'
      AND t.tgname = 'trg_audit_logs_block_update_delete'
      AND NOT t.tgisinternal
  ) INTO has_blocker;

  IF has_blocker THEN
    ALTER TABLE public.audit_logs DISABLE TRIGGER trg_audit_logs_block_update_delete;
  END IF;

  BEGIN
    ALTER TABLE public.audit_logs
      ADD COLUMN pseudonymized_at timestamptz
      GENERATED ALWAYS AS (created_at) STORED;
  EXCEPTION
    WHEN OTHERS THEN
      IF has_blocker THEN
        BEGIN
          ALTER TABLE public.audit_logs ENABLE TRIGGER trg_audit_logs_block_update_delete;
        EXCEPTION
          WHEN OTHERS THEN
            NULL;
        END;
      END IF;
      RAISE;
  END;

  IF has_blocker THEN
    ALTER TABLE public.audit_logs ENABLE TRIGGER trg_audit_logs_block_update_delete;
  END IF;
END
$audit_pseudo$;

COMMENT ON COLUMN public.audit_logs.pseudonymized_at IS
  'Igual a created_at (GENERATED STORED): audit_logs es append-only; sin UPDATE de aplicacion.';

-- 4) Estadísticas agregadas para reporting M&A (solo conteos / flags).
CREATE OR REPLACE FUNCTION public.compliance_hito_14_stats()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT jsonb_build_object(
    'usuarios_total', (SELECT count(*)::bigint FROM public.usuarios),
    'usuarios_legacy_sha256_hex', (
      SELECT count(*)::bigint FROM public.usuarios
      WHERE password_hash ~ '^[a-fA-F0-9]{64}$'
    ),
    'usuarios_argon2id', (
      SELECT count(*)::bigint FROM public.usuarios
      WHERE password_hash LIKE '$argon2id$%'
    ),
    'usuarios_needs_rehash_true', (
      SELECT count(*)::bigint FROM public.usuarios WHERE needs_rehash IS TRUE
    ),
    'usuarios_password_must_reset_true', (
      CASE
        WHEN EXISTS (
          SELECT 1
          FROM information_schema.columns
          WHERE table_schema = 'public'
            AND table_name = 'usuarios'
            AND column_name = 'password_must_reset'
        )
        THEN (
          SELECT count(*)::bigint
          FROM public.usuarios
          WHERE password_must_reset IS TRUE
        )
        ELSE NULL::bigint
      END
    ),
    'clientes_total', (SELECT count(*)::bigint FROM public.clientes),
    'clientes_pseudonymized_at_null', (
      SELECT count(*)::bigint FROM public.clientes WHERE pseudonymized_at IS NULL
    ),
    'clientes_pseudonymized_at_set', (
      SELECT count(*)::bigint FROM public.clientes WHERE pseudonymized_at IS NOT NULL
    ),
    'audit_logs_total', (SELECT count(*)::bigint FROM public.audit_logs)
  );
$$;

COMMENT ON FUNCTION public.compliance_hito_14_stats() IS
  'Conteos agregados hito 1.4 (passwords + PII metadata). Sin filas ni secretos.';

REVOKE ALL ON FUNCTION public.compliance_hito_14_stats() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.compliance_hito_14_stats() TO service_role;

-- 5) Batch: marcar needs_rehash en legacy aún inconsistente (idempotente).
CREATE OR REPLACE FUNCTION public.compliance_batch_mark_usuarios_needs_rehash(p_limit int DEFAULT 500)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  n int := 0;
BEGIN
  p_limit := greatest(1, least(coalesce(p_limit, 500), 5000));
  WITH cte AS (
    SELECT id
    FROM public.usuarios
    WHERE password_hash ~ '^[a-fA-F0-9]{64}$'
      AND needs_rehash IS NOT TRUE
    LIMIT p_limit
  )
  UPDATE public.usuarios u
  SET needs_rehash = true
  FROM cte
  WHERE u.id = cte.id;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END;
$$;

REVOKE ALL ON FUNCTION public.compliance_batch_mark_usuarios_needs_rehash(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.compliance_batch_mark_usuarios_needs_rehash(integer) TO service_role;

-- 6) Batch: sellar pseudonymized_at en clientes pendientes.
CREATE OR REPLACE FUNCTION public.compliance_batch_stamp_clientes_pseudonymized(p_limit int DEFAULT 500)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  n int := 0;
BEGIN
  p_limit := greatest(1, least(coalesce(p_limit, 500), 5000));
  WITH cte AS (
    SELECT id
    FROM public.clientes
    WHERE pseudonymized_at IS NULL
    LIMIT p_limit
  )
  UPDATE public.clientes c
  SET pseudonymized_at = now()
  FROM cte
  WHERE c.id = cte.id;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END;
$$;

REVOKE ALL ON FUNCTION public.compliance_batch_stamp_clientes_pseudonymized(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.compliance_batch_stamp_clientes_pseudonymized(integer) TO service_role;

COMMIT;
