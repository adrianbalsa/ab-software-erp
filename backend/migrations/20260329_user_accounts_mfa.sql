-- Vincular varios proveedores de identidad al mismo usuario (OIDC / password) y campos MFA (TOTP futuro).

ALTER TABLE public.usuarios
  ADD COLUMN IF NOT EXISTS mfa_enabled boolean NOT NULL DEFAULT false;

ALTER TABLE public.usuarios
  ADD COLUMN IF NOT EXISTS mfa_secret text;

COMMENT ON COLUMN public.usuarios.mfa_enabled IS 'Si true, el login exigirá segundo factor cuando se implemente TOTP';
COMMENT ON COLUMN public.usuarios.mfa_secret IS 'Secreto TOTP (base32); NULL si MFA no configurado';

CREATE TABLE IF NOT EXISTS public.user_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES public.usuarios (id) ON DELETE CASCADE,
  provider text NOT NULL,
  provider_subject text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT user_accounts_provider_subject_unique UNIQUE (provider, provider_subject),
  CONSTRAINT user_accounts_provider_chk CHECK (
    provider = ANY (ARRAY['password'::text, 'google'::text, 'microsoft'::text])
  )
);

CREATE INDEX IF NOT EXISTS idx_user_accounts_user_id ON public.user_accounts (user_id);

COMMENT ON TABLE public.user_accounts IS
  'Identidades externas vinculadas a usuarios.id (mismo usuario, varios métodos de login)';
