-- Fechas administrativas (ITV, seguro, tacógrafo) en inventario flota.
-- Compatibilidad: copia desde itv_vencimiento / seguro_vencimiento si las nuevas columnas están vacías.

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS fecha_itv date,
  ADD COLUMN IF NOT EXISTS fecha_seguro date,
  ADD COLUMN IF NOT EXISTS fecha_tacografo date;

UPDATE public.flota
SET fecha_itv = itv_vencimiento
WHERE fecha_itv IS NULL AND itv_vencimiento IS NOT NULL;

UPDATE public.flota
SET fecha_seguro = seguro_vencimiento
WHERE fecha_seguro IS NULL AND seguro_vencimiento IS NOT NULL;

COMMENT ON COLUMN public.flota.fecha_itv IS 'Próxima ITV (fecha límite); preferente sobre itv_vencimiento legacy.';
COMMENT ON COLUMN public.flota.fecha_seguro IS 'Vencimiento póliza; preferente sobre seguro_vencimiento legacy.';
COMMENT ON COLUMN public.flota.fecha_tacografo IS 'Revisión / calibración tacógrafo (fecha límite).';
