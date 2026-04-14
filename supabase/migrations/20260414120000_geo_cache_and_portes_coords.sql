-- Global geo cache (Geocoding + Routes API) for cost control. Accessed by backend (service role).
-- Portes: persisted coordinates and road distance (m) for CO₂ reporting and maps.

CREATE TABLE IF NOT EXISTS public.geo_cache (
  route_key TEXT PRIMARY KEY,
  cache_kind TEXT NOT NULL DEFAULT 'route' CHECK (cache_kind IN ('route', 'geocode')),
  origin TEXT NOT NULL,
  destination TEXT NOT NULL DEFAULT '',
  origin_norm TEXT,
  destination_norm TEXT,
  distance_meters INTEGER NOT NULL DEFAULT 0 CHECK (distance_meters >= 0),
  duration_seconds INTEGER NOT NULL DEFAULT 0 CHECK (duration_seconds >= 0),
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_geo_cache_kind_updated
  ON public.geo_cache (cache_kind, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_geo_cache_norm_pair
  ON public.geo_cache (origin_norm, destination_norm)
  WHERE cache_kind = 'route';

COMMENT ON TABLE public.geo_cache IS
  'Caché global de Geocoding y Routes API (distance_meters, duration_seconds); reduce llamadas facturables.';

ALTER TABLE public.geo_cache ENABLE ROW LEVEL SECURITY;

-- Sin datos sensibles: lectura autenticada; escritura reservada a service_role / backend.
DROP POLICY IF EXISTS geo_cache_select_authenticated ON public.geo_cache;
CREATE POLICY geo_cache_select_authenticated
  ON public.geo_cache
  FOR SELECT
  TO authenticated
  USING (true);

-- Portes: coordenadas y distancia real carretera (m).
ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS lat_origin DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS lng_origin DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS lat_dest DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS lng_dest DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS real_distance_meters DOUBLE PRECISION;

COMMENT ON COLUMN public.portes.real_distance_meters IS
  'Distancia carretera acumulada (m) vía Google Routes API; CO₂ reporting.';
