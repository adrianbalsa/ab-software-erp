-- Posición GPS en vivo (Fleet) — columnas en public.vehiculos
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vehiculos'
  ) THEN
    ALTER TABLE public.vehiculos ADD COLUMN IF NOT EXISTS ultima_latitud numeric;
    ALTER TABLE public.vehiculos ADD COLUMN IF NOT EXISTS ultima_longitud numeric;
    ALTER TABLE public.vehiculos ADD COLUMN IF NOT EXISTS ultima_actualizacion_gps timestamptz;
    COMMENT ON COLUMN public.vehiculos.ultima_latitud IS 'Última latitud WGS84 reportada por el dispositivo.';
    COMMENT ON COLUMN public.vehiculos.ultima_longitud IS 'Última longitud WGS84 reportada por el dispositivo.';
    COMMENT ON COLUMN public.vehiculos.ultima_actualizacion_gps IS 'Marca temporal UTC del último ping GPS.';
  ELSE
    RAISE NOTICE 'Omitido GPS vehiculos: tabla public.vehiculos no existe';
  END IF;
END $$;
