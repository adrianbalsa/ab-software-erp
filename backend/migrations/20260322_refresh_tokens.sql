-- =============================================================================
-- Refresh tokens (rotación) + FK a usuarios [cite: 2026-03-22]
-- Ejecutar en Supabase SQL Editor (orden: después de public.usuarios).
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.usuarios (id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked BOOLEAN NOT NULL DEFAULT FALSE,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.refresh_tokens IS
  'Sesiones OAuth-style: hash del refresh token; rotación invalida fila previa.';

CREATE UNIQUE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash
  ON public.refresh_tokens (token_hash);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_active
  ON public.refresh_tokens (user_id)
  WHERE revoked = FALSE;

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id
  ON public.refresh_tokens (user_id);
