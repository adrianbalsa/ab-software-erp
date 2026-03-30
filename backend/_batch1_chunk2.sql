table_schema = 'public' AND table_name = 'empresas' AND column_name = 'nombrelegal'
    ) AND NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'empresas' AND column_name = 'nombre_legal'
    ) THEN
      ALTER TABLE public.empresas RENAME COLUMN nombrelegal TO nombre_legal;
      RAISE NOTICE 'empresas: nombrelegal → nombre_legal';
    END IF;
  END IF;
END $$;

-- -----------------------------------------------------------------------------
-- public.flota (esquema antiguo en supabase_schema.sql vs views/flota_view.py)
-- El API espera: vehiculo, matricula, precio_compra, km_actual, estado, tipo_motor
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'flota'
  ) THEN
    -- km_actuales → km_actual
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'flota' AND column_name = 'km_actuales'
    ) AND NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'flota' AND column_name = 'km_actual'
    ) THEN
      ALTER TABLE public.flota RENAME COLUMN km_actuales TO km_actual;
      RAISE NOTICE 'flota: km_actuales → km_actual';
    END IF;
  END IF;
END $$;

-- Si tras los RENAME siguen faltando columnas que exige FlotaVehiculoOut, añádelas:
ALTER TABLE public.flota ADD COLUMN IF NOT EXISTS vehiculo text;
ALTER TABLE public.flota ADD COLUMN IF NOT EXISTS precio_compra numeric DEFAULT 0;
ALTER TABLE public.flota ADD COLUMN IF NOT EXISTS tipo_motor text;
-- Rellenar vehiculo desde marca/modelo legados si existían
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'flota' AND column_name = 'marca'
  ) AND EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'flota' AND column_name = 'modelo'
  ) THEN
    UPDATE public.flota
    SET vehiculo = NULLIF(trim(both ' ' from concat_ws(' ', nullif(trim(marca), ''), nullif(trim(modelo), ''))), '')
    WHERE (vehiculo IS NULL OR trim(vehiculo) = '');
  END IF;
END $$;

COMMENT ON COLUMN public.flota.vehiculo IS 'Denominación del vehículo (API FastAPI / Streamlit flota_view)';


-- >>> 08_20260324_esg_certificacion_vw_emissions.sql.json
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


-- >>> 09_20260324_refresh_tokens_ip_user_agent.sql.json
-- Metadatos de sesión (IP + User-Agent) [cite: 2026-03-22]
ALTER TABLE public.refresh_tokens
  ADD COLUMN IF NOT EXISTS ip_address TEXT;

ALTER TABLE public.refresh_tokens
  ADD COLUMN IF NOT EXISTS user_agent TEXT;

COMMENT ON COLUMN public.refresh_tokens.ip_address IS 'IP del cliente al crear/rotar la sesión (mejor esfuerzo; detrás de proxy usar X-Forwarded-For).';
COMMENT ON COLUMN public.refresh_tokens.user_agent IS 'Cabecera User-Agent en login/refresh.';


-- >>> 10_20260324_rls_tenant_current_empresa.sql.json
-- =============================================================================
-- RLS multi-tenant: aislar filas por contexto de sesión
-- =============================================================================
-- Alineado con `set_empresa_con