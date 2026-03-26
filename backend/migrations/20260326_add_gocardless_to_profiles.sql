-- Persistencia GoCardless para pagos automatizados (mandato SEPA / customer linking).
-- Campos críticos para el flujo de cobro automático del portal cliente.

-- 1) Profiles: referencia estable al customer remoto de GoCardless.
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS gocardless_customer_id text;

COMMENT ON COLUMN public.profiles.gocardless_customer_id IS
  'ID de customer en GoCardless (critical payment identity for automated collections).';

-- Índice único para búsquedas rápidas y evitar colisiones de customer remoto.
CREATE UNIQUE INDEX IF NOT EXISTS ux_profiles_gocardless_customer_id
  ON public.profiles (gocardless_customer_id)
  WHERE gocardless_customer_id IS NOT NULL;

-- 2) Clientes: estado de mandato activo para UX/flujo de cobro.
ALTER TABLE public.clientes
  ADD COLUMN IF NOT EXISTS mandato_activo boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.clientes.mandato_activo IS
  'TRUE cuando existe mandato SEPA activo para cobro automático vía GoCardless.';

-- 3) set_rbac_session: no requiere cambios funcionales para estos campos.
-- Ambos campos se leen/escriben dentro de filas ya protegidas por las políticas RLS
-- vigentes de profiles/clientes en base a app_current_empresa_id() y app_current_cliente_id().
COMMENT ON FUNCTION public.set_rbac_session(text, uuid, uuid, uuid) IS
  'Fija app.rbac_role, app.assigned_vehiculo_id, app.current_profile_id y app.cliente_id (portal). Compatible con campos GoCardless de profiles/clientes.';

