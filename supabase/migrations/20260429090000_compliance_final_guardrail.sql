-- =============================================================================
-- Compliance final guardrail (2026-04-29)
-- - Re-fija inmutabilidad estricta en tablas fiscales (VeriFactu / auditoría).
-- - Elimina bypass ``IF current_setting('role', true) = 'service_role'`` en
--   funciones **public** de inmutabilidad fiscal (``enforce_immutable_*``,
--   ``enforce_immutable_when_hashed``). No altera triggers de perfiles/onboarding.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1) Facturas: función estricta (misma semántica que sellado final 2026-04-28)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.enforce_immutable_facturas_strict()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF (
      COALESCE(OLD.is_finalized, false) IS TRUE
      OR (OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0)
      OR (OLD.huella_hash IS NOT NULL AND length(trim(OLD.huella_hash::text)) > 0)
      OR (OLD.fingerprint IS NOT NULL AND length(trim(OLD.fingerprint::text)) > 0)
      OR (OLD.fingerprint_hash IS NOT NULL AND length(trim(OLD.fingerprint_hash::text)) > 0)
    ) THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW_STRICT: UPDATE prohibido para factura con sellado fiscal/negocio (id=%)',
        OLD.id
        USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
  ELSIF TG_OP = 'DELETE' THEN
    IF (
      COALESCE(OLD.is_finalized, false) IS TRUE
      OR (OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0)
      OR (OLD.huella_hash IS NOT NULL AND length(trim(OLD.huella_hash::text)) > 0)
      OR (OLD.fingerprint IS NOT NULL AND length(trim(OLD.fingerprint::text)) > 0)
      OR (OLD.fingerprint_hash IS NOT NULL AND length(trim(OLD.fingerprint_hash::text)) > 0)
    ) THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW_STRICT: DELETE prohibido para factura con sellado fiscal/negocio (id=%)',
        OLD.id
        USING ERRCODE = '42501';
    END IF;
    RETURN OLD;
  END IF;

  RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS trg_facturas_immutable_hash ON public.facturas;
CREATE TRIGGER trg_facturas_immutable_hash
  BEFORE UPDATE OR DELETE ON public.facturas
  FOR EACH ROW
  EXECUTE PROCEDURE public.enforce_immutable_facturas_strict();

-- ---------------------------------------------------------------------------
-- 2) Auditoría: inmutabilidad estricta por hash_registro
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.enforce_immutable_auditoria_strict()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0 THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW_STRICT: UPDATE prohibido en auditoria con hash_registro fijado (id=%)',
        OLD.id
        USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
  ELSIF TG_OP = 'DELETE' THEN
    IF OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0 THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW_STRICT: DELETE prohibido en auditoria con hash_registro fijado (id=%)',
        OLD.id
        USING ERRCODE = '42501';
    END IF;
    RETURN OLD;
  END IF;

  RETURN COALESCE(NEW, OLD);
END;
$$;

DO $$
BEGIN
  IF to_regclass('public.auditoria') IS NOT NULL THEN
    DROP TRIGGER IF EXISTS trg_auditoria_immutable_hash ON public.auditoria;
    CREATE TRIGGER trg_auditoria_immutable_hash
      BEFORE UPDATE OR DELETE ON public.auditoria
      FOR EACH ROW
      EXECUTE PROCEDURE public.enforce_immutable_auditoria_strict();
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 3) Función genérica legacy: sin bypass por rol (misma regla que hash fijado)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.enforce_immutable_when_hashed()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0 THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW: UPDATE prohibido una vez fijado hash_registro (tabla %)',
        TG_TABLE_NAME
        USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
  ELSIF TG_OP = 'DELETE' THEN
    IF OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0 THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW: DELETE prohibido una vez fijado hash_registro (tabla %)',
        TG_TABLE_NAME
        USING ERRCODE = '42501';
    END IF;
    RETURN OLD;
  END IF;

  RETURN COALESCE(NEW, OLD);
END;
$$;

COMMENT ON FUNCTION public.enforce_immutable_when_hashed() IS
  'Bloquea UPDATE/DELETE si hash_registro está fijado; sin bypass por rol (cumplimiento AEAT).';

-- ---------------------------------------------------------------------------
-- 4) Nombre legacy ``enforce_immutable_facturas``: alineado al estricto (sin service_role)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.enforce_immutable_facturas()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF (
      COALESCE(OLD.is_finalized, false) IS TRUE
      OR (OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0)
      OR (OLD.huella_hash IS NOT NULL AND length(trim(OLD.huella_hash::text)) > 0)
      OR (OLD.fingerprint IS NOT NULL AND length(trim(OLD.fingerprint::text)) > 0)
      OR (OLD.fingerprint_hash IS NOT NULL AND length(trim(OLD.fingerprint_hash::text)) > 0)
    ) THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW_STRICT: UPDATE prohibido para factura con sellado fiscal/negocio (id=%)',
        OLD.id
        USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
  ELSIF TG_OP = 'DELETE' THEN
    IF (
      COALESCE(OLD.is_finalized, false) IS TRUE
      OR (OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0)
      OR (OLD.huella_hash IS NOT NULL AND length(trim(OLD.huella_hash::text)) > 0)
      OR (OLD.fingerprint IS NOT NULL AND length(trim(OLD.fingerprint::text)) > 0)
      OR (OLD.fingerprint_hash IS NOT NULL AND length(trim(OLD.fingerprint_hash::text)) > 0)
    ) THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW_STRICT: DELETE prohibido para factura con sellado fiscal/negocio (id=%)',
        OLD.id
        USING ERRCODE = '42501';
    END IF;
    RETURN OLD;
  END IF;

  RETURN COALESCE(NEW, OLD);
END;
$$;

-- ---------------------------------------------------------------------------
-- 5) TRUNCATE guard (re-aplicar si la tabla existe)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.prevent_truncate_immutable()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'TRUNCATE_PROHIBITED: Esta tabla contiene registros legales inalterables'
    USING ERRCODE = '42501';
END;
$$;

DROP TRIGGER IF EXISTS trg_facturas_prevent_truncate_immutable ON public.facturas;
CREATE TRIGGER trg_facturas_prevent_truncate_immutable
  BEFORE TRUNCATE ON public.facturas
  FOR EACH STATEMENT
  EXECUTE PROCEDURE public.prevent_truncate_immutable();

DO $$
BEGIN
  IF to_regclass('public.auditoria') IS NOT NULL THEN
    DROP TRIGGER IF EXISTS trg_auditoria_prevent_truncate_immutable ON public.auditoria;
    CREATE TRIGGER trg_auditoria_prevent_truncate_immutable
      BEFORE TRUNCATE ON public.auditoria
      FOR EACH STATEMENT
      EXECUTE PROCEDURE public.prevent_truncate_immutable();
  END IF;
END $$;

COMMIT;
