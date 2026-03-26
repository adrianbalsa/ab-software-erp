-- Certificación de emisiones (norma) en flota y vehículos; vista ESG.
-- Valores: Euro V, Euro VI, Electrico, Hibrido (default Euro VI).

ALTER TABLE public.vehiculos
  ADD COLUMN IF NOT EXISTS certificacion_emisiones text NOT NULL DEFAULT 'Euro VI';

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS certificacion_emisiones text NOT NULL DEFAULT 'Euro VI';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'vehiculos_certificacion_emisiones_check'
  ) THEN
    ALTER TABLE public.vehiculos
      ADD CONSTRAINT vehiculos_certificacion_emisiones_check
      CHECK (certificacion_emisiones IN ('Euro V', 'Euro VI', 'Electrico', 'Hibrido'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'flota_certificacion_emisiones_check'
  ) THEN
    ALTER TABLE public.flota
      ADD CONSTRAINT flota_certificacion_emisiones_check
      CHECK (certificacion_emisiones IN ('Euro V', 'Euro VI', 'Electrico', 'Hibrido'));
  END IF;
END $$;

COMMENT ON COLUMN public.vehiculos.certificacion_emisiones IS
  'Norma de emisiones (ESG auditoría): Euro V, Euro VI, Electrico, Hibrido';

COMMENT ON COLUMN public.flota.certificacion_emisiones IS
  'Norma de emisiones (ESG auditoría): Euro V, Euro VI, Electrico, Hibrido';

-- Detalle por porte con CO2 y certificación (filtrar por rango de fechas en consultas).
CREATE OR REPLACE VIEW public.vw_esg_emissions_summary AS
SELECT
  p.id AS porte_id,
  p.empresa_id,
  p.cliente_id,
  p.vehiculo_id,
  (p.fecha::date) AS fecha,
  COALESCE(p.co2_emitido, 0)::numeric AS co2_kg,
  COALESCE(v.certificacion_emisiones, f.certificacion_emisiones, 'Euro VI'::text) AS certificacion_emisiones
FROM public.portes p
LEFT JOIN public.vehiculos v
  ON v.id = p.vehiculo_id
  AND v.empresa_id = p.empresa_id
  AND v.deleted_at IS NULL
LEFT JOIN public.flota f
  ON f.id = p.vehiculo_id
  AND f.empresa_id = p.empresa_id
  AND f.deleted_at IS NULL
WHERE p.deleted_at IS NULL;

COMMENT ON VIEW public.vw_esg_emissions_summary IS
  'Portes con co2_kg y certificación (COALESCE vehiculos, flota, Euro VI). Filtrar fecha en WHERE.';
