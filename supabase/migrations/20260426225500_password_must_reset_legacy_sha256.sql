-- Marca cuentas que deben cambiar contraseña antes de emitir sesión.
-- Se usa para cortar el acceso con hashes legacy SHA-256 sin reescribirlos
-- automáticamente en login.

ALTER TABLE public.usuarios
  ADD COLUMN IF NOT EXISTS password_must_reset boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.usuarios.password_must_reset IS
  'Si true, el login password queda bloqueado hasta completar /api/v1/auth/reset-password';

CREATE INDEX IF NOT EXISTS idx_usuarios_password_must_reset
  ON public.usuarios (password_must_reset)
  WHERE password_must_reset IS TRUE;
