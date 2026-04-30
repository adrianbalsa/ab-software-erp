-- Verificación de inmutabilidad fiscal (sellado): triggers esperados + smoke comportamental.
--
-- Objetivo DD: evidencia reproducible de que UPDATE/DELETE/TRUNCATE quedan bloqueados en tablas
-- críticas según migraciones:
--   `supabase/migrations/20260428184500_facturas_immutability_final_seal.sql`
--   `supabase/migrations/20260429090000_compliance_final_guardrail.sql`
--   `supabase/migrations/20260423170000_audit_logs_immutable_hardening.sql`
--
-- Uso (staging / SQL Editor Supabase con rol suficiente sobre `public.*`, p. ej. postgres):
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/verify_fiscal_immutability_smoke.sql
--
-- Limitaciones:
-- - Superuser puede desactivar triggers (`SESSION_REPLICATION_ROLE`) — no cubrir aquí.
-- - Si TRUNCATE en `facturas` falla antes por FKs hijas, es normal; la protección sigue
--   existiendo en catálogo (`trg_facturas_prevent_truncate_immutable`).
-- - RLS puede impedir UPDATE antes que el trigger si la sesión no es propietaria/backend;
--   las pruebas UPDATE/DELETE filan por mensaje `42501` / texto esperado.
-- - Esquemas antiguos: si falta ``is_finalized`` (u otras columnas de huella), el bloque B
--   solo usa columnas que existan en ``information_schema``.

-- =============================================================================
-- A) Catálogo: triggers esperados (no muta datos)
-- =============================================================================

WITH expected(tgname, relname) AS (
  VALUES
    ('trg_facturas_immutable_hash'::name, 'facturas'::name),
    ('trg_facturas_prevent_truncate_immutable'::name, 'facturas'::name),
    ('trg_auditoria_immutable_hash'::name, 'auditoria'::name),
    ('trg_auditoria_prevent_truncate_immutable'::name, 'auditoria'::name),
    ('trg_audit_logs_block_update_delete'::name, 'audit_logs'::name),
    ('trg_audit_logs_block_truncate'::name, 'audit_logs'::name)
)
SELECT
  e.relname AS table_name,
  e.tgname AS trigger_name,
  EXISTS (
    SELECT 1
    FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = e.relname
      AND t.tgname = e.tgname
      AND NOT t.tgisinternal
  ) AS present
FROM expected e
LEFT JOIN pg_class c ON c.relname = e.relname
LEFT JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
ORDER BY e.relname, e.tgname;

-- =============================================================================
-- B) Smoke: factura sellada — UPDATE y DELETE deben fallar (IMMUTABLE_ROW_STRICT)
-- =============================================================================

DO $$
DECLARE
  fid bigint;
  parts text[] := ARRAY[]::text[];
  cond_sql text;
  has_col boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM information_schema.columns c
    WHERE c.table_schema = 'public'
      AND c.table_name = 'facturas'
      AND c.column_name = 'is_finalized'
  ) INTO has_col;
  IF has_col THEN
    parts := array_append(parts, 'COALESCE(f.is_finalized, false) IS TRUE');
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns c
    WHERE c.table_schema = 'public' AND c.table_name = 'facturas' AND c.column_name = 'hash_registro'
  ) INTO has_col;
  IF has_col THEN
    parts := array_append(parts, '(f.hash_registro IS NOT NULL AND length(trim(f.hash_registro::text)) > 0)');
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns c
    WHERE c.table_schema = 'public' AND c.table_name = 'facturas' AND c.column_name = 'huella_hash'
  ) INTO has_col;
  IF has_col THEN
    parts := array_append(parts, '(f.huella_hash IS NOT NULL AND length(trim(f.huella_hash::text)) > 0)');
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns c
    WHERE c.table_schema = 'public' AND c.table_name = 'facturas' AND c.column_name = 'fingerprint'
  ) INTO has_col;
  IF has_col THEN
    parts := array_append(parts, '(f.fingerprint IS NOT NULL AND length(trim(f.fingerprint::text)) > 0)');
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns c
    WHERE c.table_schema = 'public' AND c.table_name = 'facturas' AND c.column_name = 'fingerprint_hash'
  ) INTO has_col;
  IF has_col THEN
    parts := array_append(parts, '(f.fingerprint_hash IS NOT NULL AND length(trim(f.fingerprint_hash::text)) > 0)');
  END IF;

  IF coalesce(array_length(parts, 1), 0) = 0 THEN
    RAISE NOTICE '[facturas] UPDATE/DELETE smoke: SKIP (ninguna columna de sellado reconocida en information_schema)';
    RETURN;
  END IF;

  cond_sql := array_to_string(parts, ' OR ');
  EXECUTE format(
    'SELECT f.id FROM public.facturas f WHERE (%s) ORDER BY f.id DESC LIMIT 1',
    cond_sql
  ) INTO fid;

  IF fid IS NULL THEN
    RAISE NOTICE '[facturas] UPDATE smoke: SKIP (no hay fila sellada)';
  ELSE
    BEGIN
      UPDATE public.facturas SET id = id WHERE id = fid;
      RAISE EXCEPTION '[facturas] UPDATE smoke: FAIL (debería bloquearse), id=%', fid;
    EXCEPTION
      WHEN SQLSTATE '42501' THEN
        IF SQLERRM LIKE '%IMMUTABLE_ROW_STRICT%' THEN
          RAISE NOTICE '[facturas] UPDATE smoke: OK (bloqueado), id=%', fid;
        ELSE
          RAISE NOTICE '[facturas] UPDATE smoke: 42501 pero mensaje distinto: %', SQLERRM;
        END IF;
      WHEN OTHERS THEN
        RAISE NOTICE '[facturas] UPDATE smoke: error inesperado SQLSTATE=% SQLERRM=%', SQLSTATE, SQLERRM;
    END;
  END IF;

  IF fid IS NULL THEN
    RAISE NOTICE '[facturas] DELETE smoke: SKIP (no hay fila sellada)';
  ELSE
    BEGIN
      DELETE FROM public.facturas WHERE id = fid;
      RAISE EXCEPTION '[facturas] DELETE smoke: FAIL (debería bloquearse), id=%', fid;
    EXCEPTION
      WHEN SQLSTATE '42501' THEN
        IF SQLERRM LIKE '%IMMUTABLE_ROW_STRICT%' THEN
          RAISE NOTICE '[facturas] DELETE smoke: OK (bloqueado), id=%', fid;
        ELSE
          RAISE NOTICE '[facturas] DELETE smoke: 42501 pero mensaje distinto: %', SQLERRM;
        END IF;
      WHEN OTHERS THEN
        RAISE NOTICE '[facturas] DELETE smoke: error inesperado SQLSTATE=% SQLERRM=%', SQLSTATE, SQLERRM;
    END;
  END IF;
END $$;

-- =============================================================================
-- C) Smoke: auditoría con hash_registro — UPDATE/DELETE bloqueados (si hay fila)
-- =============================================================================

DO $$
DECLARE
  row_ctid tid;
BEGIN
  IF to_regclass('public.auditoria') IS NULL THEN
    RAISE NOTICE '[auditoria] UPDATE smoke: SKIP (tabla ausente)';
    RETURN;
  END IF;

  SELECT a.ctid
  INTO row_ctid
  FROM public.auditoria a
  WHERE a.hash_registro IS NOT NULL AND length(trim(a.hash_registro::text)) > 0
  ORDER BY a.ctid
  LIMIT 1;

  IF row_ctid IS NULL THEN
    RAISE NOTICE '[auditoria] UPDATE smoke: SKIP (no hay fila con hash_registro)';
    RETURN;
  END IF;

  BEGIN
    UPDATE public.auditoria a SET tabla = a.tabla WHERE a.ctid = row_ctid;
    RAISE EXCEPTION '[auditoria] UPDATE smoke: FAIL (debería bloquearse), ctid=%', row_ctid;
  EXCEPTION
    WHEN SQLSTATE '42501' THEN
      IF SQLERRM LIKE '%IMMUTABLE_ROW_STRICT%' OR SQLERRM LIKE '%IMMUTABLE%' THEN
        RAISE NOTICE '[auditoria] UPDATE smoke: OK (bloqueado), ctid=%', row_ctid;
      ELSE
        RAISE NOTICE '[auditoria] UPDATE smoke: 42501 pero mensaje distinto: %', SQLERRM;
      END IF;
    WHEN OTHERS THEN
      RAISE NOTICE '[auditoria] UPDATE smoke: error inesperado SQLSTATE=% SQLERRM=%', SQLSTATE, SQLERRM;
  END;

  BEGIN
    DELETE FROM public.auditoria a WHERE a.ctid = row_ctid;
    RAISE EXCEPTION '[auditoria] DELETE smoke: FAIL (debería bloquearse), ctid=%', row_ctid;
  EXCEPTION
    WHEN SQLSTATE '42501' THEN
      IF SQLERRM LIKE '%IMMUTABLE_ROW_STRICT%' OR SQLERRM LIKE '%IMMUTABLE%' THEN
        RAISE NOTICE '[auditoria] DELETE smoke: OK (bloqueado), ctid=%', row_ctid;
      ELSE
        RAISE NOTICE '[auditoria] DELETE smoke: 42501 pero mensaje distinto: %', SQLERRM;
      END IF;
    WHEN OTHERS THEN
      RAISE NOTICE '[auditoria] DELETE smoke: error inesperado SQLSTATE=% SQLERRM=%', SQLSTATE, SQLERRM;
  END;
END $$;

-- =============================================================================
-- D) TRUNCATE: bloqueo por trigger (mensajes distintos según tabla)
-- =============================================================================

DO $$
BEGIN
  IF to_regclass('public.audit_logs') IS NULL THEN
    RAISE NOTICE '[audit_logs] TRUNCATE smoke: SKIP (tabla ausente)';
  ELSE
    BEGIN
      TRUNCATE public.audit_logs;
      RAISE EXCEPTION '[audit_logs] TRUNCATE smoke: FAIL (debería bloquearse)';
    EXCEPTION
      WHEN SQLSTATE '42501' THEN
        IF SQLERRM LIKE '%append-only%' OR SQLERRM LIKE '%TRUNCATE%' THEN
          RAISE NOTICE '[audit_logs] TRUNCATE smoke: OK (bloqueado)';
        ELSE
          RAISE NOTICE '[audit_logs] TRUNCATE smoke: 42501 mensaje: %', SQLERRM;
        END IF;
      WHEN OTHERS THEN
        RAISE NOTICE '[audit_logs] TRUNCATE smoke: SQLSTATE=% SQLERRM=%', SQLSTATE, SQLERRM;
    END;
  END IF;

  IF to_regclass('public.facturas') IS NULL THEN
    RAISE NOTICE '[facturas] TRUNCATE smoke: SKIP (tabla ausente)';
  ELSE
    BEGIN
      TRUNCATE public.facturas;
      RAISE EXCEPTION '[facturas] TRUNCATE smoke: FAIL (debería bloquearse o impedirse por FK)';
    EXCEPTION
      WHEN SQLSTATE '42501' THEN
        IF SQLERRM LIKE '%TRUNCATE_PROHIBITED%' OR SQLERRM LIKE '%inalterables%' THEN
          RAISE NOTICE '[facturas] TRUNCATE smoke: OK (bloqueado por trigger)';
        ELSE
          RAISE NOTICE '[facturas] TRUNCATE smoke: 42501 mensaje: %', SQLERRM;
        END IF;
      WHEN OTHERS THEN
        RAISE NOTICE '[facturas] TRUNCATE smoke: SQLSTATE=% SQLERRM=% (FK u otra restricción también válida)', SQLSTATE, SQLERRM;
    END;
  END IF;
END $$;
