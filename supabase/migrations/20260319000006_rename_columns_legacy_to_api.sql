-- =============================================================================
-- Sincronización columnas PostgreSQL (producción) → nombres esperados por el
-- backend FastAPI / PostgREST (consultas en app/services/* y schemas Pydantic).
--
-- Empresas: el API y el Panel Admin usan snake_case (`nombre_legal`, `nombre_comercial`).
-- Si aún existen columnas legadas sin guiones (`nombrelegal`, `nombrecomercial`),
-- este bloque las renombra.
--
-- Ejecutar en Supabase SQL Editor (producción). Idempotente: no falla si ya
-- están alineados. Revisa vistas/materialized views que referencien los nombres
-- antiguos y recréalas si aplica.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- public.empresas
-- -----------------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'empresas'
  ) THEN
    -- nombrecomercial → nombre_comercial
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'empresas' AND column_name = 'nombrecomercial'
    ) AND NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'empresas' AND column_name = 'nombre_comercial'
    ) THEN
      ALTER TABLE public.empresas RENAME COLUMN nombrecomercial TO nombre_comercial;
      RAISE NOTICE 'empresas: nombrecomercial → nombre_comercial';
    END IF;

    -- nombrelegal → nombre_legal
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'empresas' AND column_name = 'nombrelegal'
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
