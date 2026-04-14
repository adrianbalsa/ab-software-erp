-- ESG: factor de emisión por vehículo (kg CO₂ / (t·km)) y asignación opcional de porte → flota.
ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS factor_emision_co2_tkm NUMERIC(14, 8);

COMMENT ON COLUMN public.flota.factor_emision_co2_tkm IS
  'Opcional: factor kg CO₂eq por tonelada·km; si NULL se deriva de tipo_motor en la API.';

ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS vehiculo_id UUID REFERENCES public.flota (id);

CREATE INDEX IF NOT EXISTS idx_portes_vehiculo_id
  ON public.portes (vehiculo_id)
  WHERE vehiculo_id IS NOT NULL;

COMMENT ON COLUMN public.portes.vehiculo_id IS
  'Vehículo asignado al porte (ESG); NULL = factor global empresa.';
