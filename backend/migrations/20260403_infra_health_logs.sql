-- Logs proactivos de salud (latencia DB, peticiones lentas). Sin credenciales en `message`.
CREATE TABLE IF NOT EXISTS public.infra_health_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  source text NOT NULL,
  status text NOT NULL,
  latency_ms double precision,
  message text,
  path text,
  method text
);

CREATE INDEX IF NOT EXISTS infra_health_logs_created_at_idx
  ON public.infra_health_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS infra_health_logs_source_idx
  ON public.infra_health_logs (source);

COMMENT ON TABLE public.infra_health_logs IS
  'SRE: salud DB y latencia API; los mensajes deben estar sanitizados (sin URI con contraseña).';
