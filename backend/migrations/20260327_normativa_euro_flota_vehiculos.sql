-- Normativa EURO explícita para factores CO₂ por vehículo (ESG engine).
-- Complementa certificacion_emisiones (auditoría / legacy) sin sustituirla.

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS normativa_euro text NOT NULL DEFAULT 'Euro VI';

ALTER TABLE public.vehiculos
  ADD COLUMN IF NOT EXISTS normativa_euro text NOT NULL DEFAULT 'Euro VI';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'flota_normativa_euro_check'
  ) THEN
    ALTER TABLE public.flota
      ADD CONSTRAINT flota_normativa_euro_check
      CHECK (normativa_euro IN ('Euro IV', 'Euro V', 'Euro VI'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'vehiculos_normativa_euro_check'
  ) THEN
    ALTER TABLE public.vehiculos
      ADD CONSTRAINT vehiculos_normativa_euro_check
      CHECK (normativa_euro IN ('Euro IV', 'Euro V', 'Euro VI'));
  END IF;
END $$;

COMMENT ON COLUMN public.flota.normativa_euro IS
  'Norma EURO para factor kg CO2/km (ESG). Sincronizada conceptualmente con certificacion_emisiones cuando aplica.';

COMMENT ON COLUMN public.vehiculos.normativa_euro IS
  'Norma EURO para factor kg CO2/km (ESG).';

-- Backfill conservador desde certificación histórica (Euro IV no existía en el check antiguo → Euro VI salvo Euro V/VI).
UPDATE public.flota
SET normativa_euro = CASE trim(coalesce(certificacion_emisiones, ''))
  WHEN 'Euro V' THEN 'Euro V'
  WHEN 'Euro VI' THEN 'Euro VI'
  ELSE 'Euro VI'
END
WHERE normativa_euro = 'Euro VI';

UPDATE public.vehiculos
SET normativa_euro = CASE trim(coalesce(certificacion_emisiones, ''))
  WHEN 'Euro V' THEN 'Euro V'
  WHEN 'Euro VI' THEN 'Euro VI'
  ELSE 'Euro VI'
END
WHERE normativa_euro = 'Euro VI';
