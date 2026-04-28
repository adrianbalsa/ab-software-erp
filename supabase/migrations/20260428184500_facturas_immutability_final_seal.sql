BEGIN;

-- ============================================================================
-- Facturas immutability final seal
-- - Cierra bypasses de inmutabilidad por estado/huella extendida.
-- - Sin excepciones por rol (incluido service_role).
-- - Añade blindaje anti-TRUNCATE para facturas y auditoria.
-- ============================================================================

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
