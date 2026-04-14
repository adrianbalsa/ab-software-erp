-- Vencimientos ITV / seguro para alertas de flota [cite: 2026-03-22]
-- km_proximo_servicio ya existe en esquema legacy (supabase_schema.sql).

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS itv_vencimiento date;

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS seguro_vencimiento date;

COMMENT ON COLUMN public.flota.itv_vencimiento IS 'Próxima ITV (fecha límite)';
COMMENT ON COLUMN public.flota.seguro_vencimiento IS 'Vencimiento póliza seguro';
