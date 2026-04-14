-- Campos VeriFactu / SIF para tabla facturas (ejecutar en Supabase si aún no existen).

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS tipo_factura text;

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS num_factura text;

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS nif_emisor text;

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS hash_registro text;

COMMENT ON COLUMN public.facturas.tipo_factura IS 'p.ej. F1 factura completa (VeriFactu)';
COMMENT ON COLUMN public.facturas.num_factura IS 'Serie-Año-Secuencial';
COMMENT ON COLUMN public.facturas.nif_emisor IS 'NIF obligado tributario (empresa)';
COMMENT ON COLUMN public.facturas.hash_registro IS 'SHA-256 huella de registro (encadenamiento)';
