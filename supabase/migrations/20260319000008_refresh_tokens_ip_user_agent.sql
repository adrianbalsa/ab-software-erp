-- Metadatos de sesión (IP + User-Agent) [cite: 2026-03-22]
ALTER TABLE public.refresh_tokens
  ADD COLUMN IF NOT EXISTS ip_address TEXT;

ALTER TABLE public.refresh_tokens
  ADD COLUMN IF NOT EXISTS user_agent TEXT;

COMMENT ON COLUMN public.refresh_tokens.ip_address IS 'IP del cliente al crear/rotar la sesión (mejor esfuerzo; detrás de proxy usar X-Forwarded-For).';
COMMENT ON COLUMN public.refresh_tokens.user_agent IS 'Cabecera User-Agent en login/refresh.';
