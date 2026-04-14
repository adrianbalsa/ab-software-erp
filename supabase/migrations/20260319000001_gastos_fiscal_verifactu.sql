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
