-- Caché global de distancias Google Distance Matrix (reduce costes API).
CREATE TABLE IF NOT EXISTS public.maps_distance_cache (
  id BIGSERIAL PRIMARY KEY,
  cache_key TEXT NOT NULL UNIQUE,
  origin TEXT NOT NULL,
  destination TEXT NOT NULL,
  distance_km NUMERIC(12, 4) NOT NULL CHECK (distance_km >= 0),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_maps_distance_cache_updated
  ON public.maps_distance_cache (updated_at DESC);

COMMENT ON TABLE public.maps_distance_cache IS
  'Caché de distancias carretera (km) entre origen/destino; clave hash normalizada.';

ALTER TABLE public.maps_distance_cache ENABLE ROW LEVEL SECURITY;

-- Lectura/escritura para cualquier rol autenticado (JWT); la clave no expone secretos.
DROP POLICY IF EXISTS maps_distance_cache_authenticated_all ON public.maps_distance_cache;
CREATE POLICY maps_distance_cache_authenticated_all
  ON public.maps_distance_cache
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);
