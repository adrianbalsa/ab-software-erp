” en este proyecto) ────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'flota'
  ) THEN
    ALTER TABLE public.flota ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS flota_tenant_all ON public.flota;
    DROP POLICY IF EXISTS flota_select_tenant ON public.flota;
    DROP POLICY IF EXISTS flota_insert_tenant ON public.flota;
    DROP POLICY IF EXISTS flota_update_tenant ON public.flota;
    DROP POLICY IF EXISTS flota_delete_tenant ON public.flota;

    CREATE POLICY flota_select_tenant ON public.flota
      FOR SELECT
      USING (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY flota_insert_tenant ON public.flota
      FOR INSERT
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY flota_update_tenant ON public.flota
      FOR UPDATE
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY flota_delete_tenant ON public.flota
      FOR DELETE
      USING (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;

-- ─── AUDITORÍA: cuatro políticas (requiere empresa_id NOT NULL) ───────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'auditoria'
  ) THEN
    ALTER TABLE public.auditoria ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS auditoria_tenant_all ON public.auditoria;
    DROP POLICY IF EXISTS auditoria_select_tenant ON public.auditoria;
    DROP POLICY IF EXISTS auditoria_insert_tenant ON public.auditoria;
    DROP POLICY IF EXISTS auditoria_update_tenant ON public.auditoria;
    DROP POLICY IF EXISTS auditoria_delete_tenant ON public.auditoria;

    CREATE POLICY auditoria_select_tenant ON public.auditoria
      FOR SELECT
      USING (
        empresa_id IS NOT NULL
        AND empresa_id::text = public.app_current_empresa_id()::text
      );

    CREATE POLICY auditoria_insert_tenant ON public.auditoria
      FOR INSERT
      WITH CHECK (
        empresa_id IS NOT NULL
        AND empresa_id::text = public.app_current_empresa_id()::text
      );

    CREATE POLICY auditoria_update_tenant ON public.auditoria
      FOR UPDATE
      USING (
        empresa_id IS NOT NULL
        AND empresa_id::text = public.app_current_empresa_id()::text
      )
      WITH CHECK (
        empresa_id IS NOT NULL
        AND empresa_id::text = public.app_current_empresa_id()::text
      );

    CREATE POLICY auditoria_delete_tenant ON public.auditoria
      FOR DELETE
      USING (
        empresa_id IS NOT NULL
        AND empresa_id::text = public.app_current_empresa_id()::text
      );
  END IF;
END $$;

-- ─── PROFILES: inmutabilidad de empresa_id salvo service_role / superadmin ─
-- Supabase: sesiones `authenticated` no pueden reasignar tenant.
-- service_role (backend con clave service) bypass RLS pero el trigger sigue siendo
-- útil si se escribe con un rol que no bypass; para DEFINER clarity usamos auth.role().

CREATE OR REPLACE FUNCTION public.profiles_block_empresa_id_escalation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  jwt jsonb;
  is_superadmin boolean;
BEGIN
  IF TG_OP <> 'UPDATE' THEN
    RETURN NEW;
  END IF;

  IF NEW.empresa_id IS NOT DISTINCT FROM OLD.empresa_id THEN
    RETURN NEW;
  END IF;

  -- Rol de conexión Postgres (PostgREST / pooler)
  IF current_setting('role', true) = 'service_role' THEN
    RETURN NEW;
  END IF;

  -- Superadmin vía JWT (configurar en Supabase Auth → User → app_metadata)
  BEGIN
    jwt := auth.jwt();
  EXCEPTION WHEN OTHERS THEN
    jwt := NULL;
  END;

  is_superadmin := coalesce((jwt -> 'app_metadata' ->> 'is_superadmin')::boolean, false)
    OR lower(coalesce(jwt -> 'app_metadata' ->> 'role', '')) = 'superadmin';

  IF is_superadmin THEN
    RETURN NEW;
  END IF;

  RAISE EXCEPTION
    'SECURITY: empresa_id en profiles no es editable para este rol. Use service_role o app_metadata.is_superadmin.';
END;
$$;

COMMENT ON FUNCTION public.profiles_block_empresa_id_escalation() IS
  'Impide cambiar profiles.empresa_id salvo service_role o JWT app_metadata.is_superadmin / role=superadmin.';

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'profiles'
  ) THEN
    DROP TRIGGER IF EXISTS trg_profiles_block_empresa_id ON public.profiles;
    CREATE TRIGGER trg_profiles_block_empresa_id
      BEFORE UPDATE ON public.profiles
      FOR EACH ROW
      EXECUTE PROCEDURE public.profiles_block_empresa_id_escalation();

    -- Políticas mínimas recomendadas (ajusta según tu modelo de signup)
    ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

    DROP POLICY IF EXISTS profiles_select_authenticated ON public.profiles;
    CREATE POLICY profiles_select_authenticated ON public.profiles
      FOR SELECT
      TO authenticated
      USING (auth.uid() = id);

    DROP POLICY IF EXISTS profiles_update_authenticated ON public.profiles;
    CREATE POLICY profiles_update_authenticated ON public.profiles
      FOR UPDATE
      TO authenticated
      USING (auth.uid() = id)
      WITH CHECK (auth.uid() = id);
  ELSE
    RAISE NOTICE 'Tabla public.profiles no existe: omitido trigger RLS profiles';
  END IF;
END $$;
