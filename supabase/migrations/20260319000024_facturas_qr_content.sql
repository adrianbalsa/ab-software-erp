BEGIN;

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS qr_content text;

COMMENT ON COLUMN public.facturas.qr_content IS
  'URL completa codificada en el QR VeriFactu (incluye hc con 8 chars de huella_hash).';

COMMIT;
