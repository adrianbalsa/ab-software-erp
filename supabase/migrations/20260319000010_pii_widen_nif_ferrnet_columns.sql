-- PII encryption compatibility: Fernet tokens are longer than legacy VARCHAR limits.
-- We widen these columns to `text` so encrypted values can be persisted safely.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'empresas'
      AND column_name = 'nif'
  ) THEN
    ALTER TABLE public.empresas ALTER COLUMN nif TYPE text;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'facturas'
      AND column_name = 'nif_emisor'
  ) THEN
    ALTER TABLE public.facturas ALTER COLUMN nif_emisor TYPE text;
  END IF;
END $$;

