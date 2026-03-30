-- Fase 2: campos fiscales para trazabilidad (VeriFactu / ticket).
-- Ejecutar en Supabase SQL Editor si la tabla `gastos` aún no los tiene.

ALTER TABLE public.gastos
  ADD COLUMN IF NOT EXISTS nif_proveedor text;

ALTER TABLE public.gastos
  ADD COLUMN IF NOT EXISTS iva numeric;

ALTER TABLE public.gastos
  ADD COLUMN IF NOT EXISTS total_eur numeric;

COMMENT ON COLUMN public.gastos.nif_proveedor IS 'NIF/CIF del proveedor (ticket/factura simplificada)';
COMMENT ON COLUMN public.gastos.iva IS 'Cuota de IVA en EUR cuando conste en el documento';
COMMENT ON COLUMN public.gastos.total_eur IS 'Importe total del gasto en EUR (referencia para reporting y cumplimiento)';


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
