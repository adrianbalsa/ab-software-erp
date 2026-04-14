-- Webhooks: columnas explícitas (secret_key, event_types, is_active), índice parcial,
-- rol developer (integraciones API) y sesión RBAC alineada.

-- ─── Enum user_role: developer ───
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
             WHERE n.nspname = 'public' AND t.typname = 'user_role')
     AND NOT EXISTS (
       SELECT 1 FROM pg_enum e
       JOIN pg_type t ON t.oid = e.enumtypid
       JOIN pg_namespace n ON n.oid = t.typnamespace
       WHERE n.nspname = 'public' AND t.typname = 'user_role' AND e.enumlabel = 'developer'
     ) THEN
    ALTER TYPE public.user_role ADD VALUE 'developer';
  END IF;
END $$;

-- ─── webhook_endpoints: renombrar columnas legacy ───
DO $$
BEGIN
  IF to_regclass('public.webhook_endpoints') IS NULL THEN
    RETURN;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'webhook_endpoints' AND column_name = 'secret'
  ) THEN
    ALTER TABLE public.webhook_endpoints RENAME COLUMN secret TO secret_key;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'webhook_endpoints' AND column_name = 'events'
  ) THEN
    ALTER TABLE public.webhook_endpoints RENAME COLUMN events TO event_types;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'webhook_endpoints' AND column_name = 'active'
  ) THEN
    ALTER TABLE public.webhook_endpoints RENAME COLUMN active TO is_active;
  END IF;
END $$;

DROP INDEX IF EXISTS public.idx_webhook_endpoints_empresa_active;
CREATE INDEX IF NOT EXISTS idx_webhook_endpoints_empresa_active
  ON public.webhook_endpoints (empresa_id)
  WHERE is_active = true;

COMMENT ON COLUMN public.webhook_endpoints.secret_key IS 'Secreto HMAC-SHA256 para cabecera X-ABLogistics-Signature.';
COMMENT ON COLUMN public.webhook_endpoints.event_types IS 'Lista de eventos suscritos o * para todos.';
COMMENT ON COLUMN public.webhook_endpoints.is_active IS 'Si false, no se entregan notificaciones.';

-- ─── Sesión RBAC: permitir developer ───
CREATE OR REPLACE FUNCTION public.set_rbac_session(
  p_rbac_role text,
  p_assigned_vehiculo_id uuid DEFAULT NULL,
  p_profile_id uuid DEFAULT NULL,
  p_cliente_id uuid DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  r text;
BEGIN
  r := lower(trim(both from coalesce(p_rbac_role, 'owner')));
  IF r NOT IN ('owner', 'traffic_manager', 'driver', 'cliente', 'developer') THEN
    r := 'owner';
  END IF;
  PERFORM set_config('app.rbac_role', r, true);
  IF p_assigned_vehiculo_id IS NULL THEN
    PERFORM set_config('app.assigned_vehiculo_id', '', true);
  ELSE
    PERFORM set_config('app.assigned_vehiculo_id', p_assigned_vehiculo_id::text, true);
  END IF;
  IF p_profile_id IS NULL THEN
    PERFORM set_config('app.current_profile_id', '', true);
  ELSE
    PERFORM set_config('app.current_profile_id', p_profile_id::text, true);
  END IF;
  IF r = 'cliente' AND p_cliente_id IS NOT NULL THEN
    PERFORM set_config('app.cliente_id', p_cliente_id::text, true);
  ELSE
    PERFORM set_config('app.cliente_id', '', true);
  END IF;
END;
$$;

COMMENT ON FUNCTION public.set_rbac_session(text, uuid, uuid, uuid) IS
  'Fija app.rbac_role (owner|traffic_manager|driver|cliente|developer), vehículo, perfil y cliente portal.';
