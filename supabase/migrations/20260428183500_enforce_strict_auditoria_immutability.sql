BEGIN;

-- Inmutabilidad estricta para public.auditoria (sin excepciones por rol):
-- si un registro ya tiene hash_registro, no se permite UPDATE ni DELETE.
DO $$
BEGIN
  IF to_regclass('public.auditoria') IS NULL THEN
    RETURN;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'auditoria'
      AND column_name = 'hash_registro'
  ) THEN
    ALTER TABLE public.auditoria
      ADD COLUMN hash_registro text;
  END IF;
END $$;

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

DROP TRIGGER IF EXISTS trg_auditoria_immutable_hash ON public.auditoria;
CREATE TRIGGER trg_auditoria_immutable_hash
  BEFORE UPDATE OR DELETE ON public.auditoria
  FOR EACH ROW
  EXECUTE PROCEDURE public.enforce_immutable_auditoria_strict();

COMMIT;
