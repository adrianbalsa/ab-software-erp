-- =============================================================================
-- RBAC empresarial: tipo user_role, perfiles operativos, sesión app.rbac_role
-- y políticas RLS en public.portes (owner/traffic_manager vs driver).
-- Requisitos: public.set_empresa_context (20260324) y conexión PostgREST con
-- el JWT del usuario para que el backend invoque set_empresa_context + set_rbac_session.
-- =============================================================================

DO $$ BEGIN
  CREATE TYPE public.user_role AS ENUM ('owner', 'traffic_manager', 'driver');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'profiles'
  ) THEN
    ALTER TABLE public.profiles
      ADD COLUMN IF NOT EXISTS role public.user_role NOT NULL DEFAULT 'owner'::public.user_role;
    ALTER TABLE public.profiles
      ADD COLUMN IF NOT EXISTS assigned_vehiculo_id UUID REFERENCES public.flota (id) ON DELETE SET NULL;

    COMMENT ON COLUMN public.profiles.role IS
      'Rol RBAC operativo: owner (total), traffic_manager (operativo sin facturación global), driver (solo lectura portes asignados).';
    COMMENT ON COLUMN public.profiles.assigned_vehiculo_id IS
      'Vehículo (flota) asignado al chófer; obligatorio para aislar filas portes vía RLS si role=driver.';

    -- Histórico: conservar privilegios (equivalente a owner operativo hasta reasignación).
    -- Nuevos registros pueden fijar role en la app; DEFAULT owner mantiene compatibilidad Zero-Downtime.
  END IF;
END $$;

-- Variables de sesión (misma transacción que set_empresa_context en la petición API).
CREATE OR REPLACE FUNCTION public.set_rbac_session(
  p_rbac_role text,
  p_assigned_vehiculo_id uuid DEFAULT NULL
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
  IF r NOT IN ('owner', 'traffic_manager', 'driver') THEN
    r := 'owner';
  END IF;
  PERFORM set_config('app.rbac_role', r, true);
  IF p_assigned_vehiculo_id IS NULL THEN
    PERFORM set_config('app.assigned_vehiculo_id', '', true);
  ELSE
    PERFORM set_config('app.assigned_vehiculo_id', p_assigned_vehiculo_id::text, true);
  END IF;
END;
$$;

COMMENT ON FUNCTION public.set_rbac_session(text, uuid) IS
  'Fija app.rbac_role y app.assigned_vehiculo_id para políticas RLS (invocar tras set_empresa_context).';

CREATE OR REPLACE FUNCTION public.app_rbac_role()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT COALESCE(
    NULLIF(trim(both from current_setting('app.rbac_role', true)), ''),
    'owner'
  );
$$;

CREATE OR REPLACE FUNCTION public.app_assigned_vehiculo_id()
RETURNS uuid
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  s text;
BEGIN
  s := NULLIF(trim(both from current_setting('app.assigned_vehiculo_id', true)), '');
  IF s IS NULL OR s = '' THEN
    RETURN NULL;
  END IF;
  RETURN s::uuid;
EXCEPTION
  WHEN invalid_text_representation THEN
    RETURN NULL;
END;
$$;

-- ─── PORTES: políticas RBAC ────────────────────────────────────────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'portes'
  ) THEN
    ALTER TABLE public.portes ENABLE ROW LEVEL SECURITY;

    DROP POLICY IF EXISTS portes_select_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_insert_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_update_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_delete_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_select_rbac ON public.portes;
    DROP POLICY IF EXISTS portes_insert_rbac ON public.portes;
    DROP POLICY IF EXISTS portes_update_rbac ON public.portes;
    DROP POLICY IF EXISTS portes_delete_rbac ON public.portes;

    CREATE POLICY portes_select_rbac ON public.portes
      FOR SELECT
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND (
          public.app_rbac_role() IN ('owner', 'traffic_manager')
          OR (
            public.app_rbac_role() = 'driver'
            AND vehiculo_id IS NOT NULL
            AND vehiculo_id = public.app_assigned_vehiculo_id()
            AND public.app_assigned_vehiculo_id() IS NOT NULL
          )
        )
      );

    CREATE POLICY portes_insert_rbac ON public.portes
      FOR INSERT
      WITH CHECK (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );

    CREATE POLICY portes_update_rbac ON public.portes
      FOR UPDATE
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      )
      WITH CHECK (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );

    CREATE POLICY portes_delete_rbac ON public.portes
      FOR DELETE
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );
  END IF;
END $$;
