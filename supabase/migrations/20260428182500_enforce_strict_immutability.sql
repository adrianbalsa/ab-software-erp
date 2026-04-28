BEGIN;

-- Inmutabilidad estricta de facturas emitidas:
-- si existe hash_registro o huella_hash, no se permite UPDATE/DELETE
-- para ningun rol (incluido service_role).
CREATE OR REPLACE FUNCTION public.enforce_immutable_facturas_strict()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF (
      (OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0)
      OR
      (OLD.huella_hash IS NOT NULL AND length(trim(OLD.huella_hash::text)) > 0)
    ) THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW_STRICT: UPDATE prohibido para factura con huella fiscal fijada (id=%)',
        OLD.id
        USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
  ELSIF TG_OP = 'DELETE' THEN
    IF (
      (OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0)
      OR
      (OLD.huella_hash IS NOT NULL AND length(trim(OLD.huella_hash::text)) > 0)
    ) THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW_STRICT: DELETE prohibido para factura con huella fiscal fijada (id=%)',
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

COMMIT;
