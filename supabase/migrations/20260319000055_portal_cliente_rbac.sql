-- Portal cliente (autoservicio): rol `cliente`, `profiles.cliente_id`, sesión app.cliente_id
-- y políticas RLS para portes/facturas/clientes sin fugas entre cargadores del mismo tenant.

-- ─── Enum user_role: valor cliente ───
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
             WHERE n.nspname = 'public' AND t.typname = 'user_role')
     AND NOT EXISTS (
       SELECT 1 FROM pg_enum e
       JOIN pg_type t ON t.oid = e.enumtypid
       JOIN pg_namespace n ON n.oid = t.typnamespace
       WHERE n.nspname = 'public' AND t.typname = 'user_role' AND e.enumlabel = 'cliente'
     ) THEN
    ALTER TYPE public.user_role ADD VALUE 'cliente';
  END IF;
END $$;

-- ─── Perfil: vínculo al maestro clientes (portal) ───
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'profiles'
  ) THEN
    ALTER TABLE public.profiles
      ADD COLUMN IF NOT EXISTS cliente_id uuid REFERENCES public.clientes (id) ON DELETE SET NULL;
    COMMENT ON COLUMN public.profiles.cliente_id IS
      'FK clientes: usuario portal (rol cliente) asociado a un cargador concreto del tenant.';
  END IF;
END $$;

-- ─── Sesión: app.cliente_id + set_rbac_session extendido ───
CREATE OR REPLACE FUNCTION public.app_current_cliente_id()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(trim(both from current_setting('app.cliente_id', true)), '');
$$;

COMMENT ON FUNCTION public.app_current_cliente_id() IS
  'UUID texto del cliente (cargador) en sesión portal; vacío si no aplica.';

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
  IF r NOT IN ('owner', 'traffic_manager', 'driver', 'cliente') THEN
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
  'Fija app.rbac_role, app.assigned_vehiculo_id, app.current_profile_id y app.cliente_id (portal).';

-- ─── PORTES: lectura para rol cliente (solo su cliente_id) ───
DO $$
BEGIN
  IF to_regclass('public.portes') IS NOT NULL THEN
    DROP POLICY IF EXISTS portes_select_cliente ON public.portes;
    CREATE POLICY portes_select_cliente ON public.portes
      FOR SELECT
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() = 'cliente'
        AND cliente_id IS NOT NULL
        AND cliente_id::text = public.app_current_cliente_id()
      );
  END IF;
END $$;

-- ─── FACTURAS: reemplazar política amplia por RBAC + portal ───
DO $$
BEGIN
  IF to_regclass('public.facturas') IS NOT NULL THEN
    DROP POLICY IF EXISTS facturas_tenant_all ON public.facturas;

    CREATE POLICY facturas_select_rbac ON public.facturas
      FOR SELECT
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND (
          public.app_rbac_role() IN ('owner', 'traffic_manager', 'driver')
          OR (
            public.app_rbac_role() = 'cliente'
            AND cliente IS NOT NULL
            AND cliente::text = public.app_current_cliente_id()
          )
        )
      );

    CREATE POLICY facturas_insert_rbac ON public.facturas
      FOR INSERT
      TO authenticated
      WITH CHECK (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );

    CREATE POLICY facturas_update_rbac ON public.facturas
      FOR UPDATE
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      )
      WITH CHECK (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );

    CREATE POLICY facturas_delete_rbac ON public.facturas
      FOR DELETE
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );
  END IF;
END $$;

-- ─── CLIENTES: staff vs portal (evitar listar todos los clientes del tenant) ───
DO $$
BEGIN
  IF to_regclass('public.clientes') IS NOT NULL THEN
    DROP POLICY IF EXISTS clientes_tenant_all ON public.clientes;

    CREATE POLICY clientes_select_staff ON public.clientes
      FOR SELECT
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager', 'driver')
      );

    CREATE POLICY clientes_select_portal ON public.clientes
      FOR SELECT
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() = 'cliente'
        AND id::text = public.app_current_cliente_id()
      );

    CREATE POLICY clientes_insert_staff ON public.clientes
      FOR INSERT
      TO authenticated
      WITH CHECK (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );

    CREATE POLICY clientes_update_staff ON public.clientes
      FOR UPDATE
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      )
      WITH CHECK (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );

    CREATE POLICY clientes_delete_staff ON public.clientes
      FOR DELETE
      TO authenticated
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );
  END IF;
END $$;
