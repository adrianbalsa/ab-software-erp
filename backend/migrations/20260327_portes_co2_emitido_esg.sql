-- Huella CO2 por porte (motor ESG Enterprise): kg CO2 estimados (distancia × toneladas × factor).
ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS co2_emitido numeric;

ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS peso_ton numeric;

COMMENT ON COLUMN public.portes.co2_emitido IS
  'kg CO2 estimados (Enterprise): distancia_km × peso_ton × factor_emision; ver eco_service.calcular_huella_porte';

COMMENT ON COLUMN public.portes.peso_ton IS
  'Toneladas de carga (opcional API); si NULL, se estima desde bultos al calcular huella.';
