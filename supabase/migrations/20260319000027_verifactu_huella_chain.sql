BEGIN;

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS huella_hash varchar(64),
  ADD COLUMN IF NOT EXISTS huella_anterior varchar(64),
  ADD COLUMN IF NOT EXISTS fecha_hitos_verifactu timestamptz;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ux_facturas_empresa_huella_hash'
  ) THEN
    ALTER TABLE public.facturas
      ADD CONSTRAINT ux_facturas_empresa_huella_hash
      UNIQUE (empresa_id, huella_hash);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_facturas_empresa_huella_seq
  ON public.facturas (empresa_id, numero_secuencial DESC);

UPDATE public.facturas
SET
  huella_hash = COALESCE(NULLIF(TRIM(huella_hash), ''), NULLIF(TRIM(hash_registro), ''), NULLIF(TRIM(hash_factura), '')),
  huella_anterior = COALESCE(NULLIF(TRIM(huella_anterior), ''), NULLIF(TRIM(hash_anterior), '')),
  fecha_hitos_verifactu = COALESCE(fecha_hitos_verifactu, now())
WHERE
  huella_hash IS NULL
  OR huella_anterior IS NULL
  OR fecha_hitos_verifactu IS NULL;

COMMIT;
