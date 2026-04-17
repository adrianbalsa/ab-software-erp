-- Multi-IVA VeriFactu: persist MathEngine desglose (tipos/string JSON for decimal-safe round-trip).
ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS desglose_por_tipo jsonb;

COMMENT ON COLUMN public.facturas.desglose_por_tipo IS
  'Desglose por tipo impositivo (JSON array); importes como cadenas decimal (2 dp HALF_EVEN).';
