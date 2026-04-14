-- ============================================================================
-- Consolidated RBAC + RLS baseline
-- - Removes migration drift by recreating policies from scratch
-- - Tenant isolation is strictly JWT based:
--     (auth.jwt() ->> 'empresa_id')::uuid = <table>.empresa_id
-- - Role enforcement is JWT based via claim "role"
-- ============================================================================

-- Helper: normalized role from JWT.
CREATE OR REPLACE FUNCTION public.jwt_role()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT lower(trim(both from coalesce(auth.jwt() ->> 'role', '')));
$$;

COMMENT ON FUNCTION public.jwt_role() IS
  'Normalized RBAC role from JWT claim `role`.';

-- Drop all existing policies for target tables.
DO $$
DECLARE
  _table text;
  _policy text;
BEGIN
  FOREACH _table IN ARRAY ARRAY['portes', 'factores_emision', 'geo_cache', 'profiles']
  LOOP
    IF to_regclass(format('public.%I', _table)) IS NULL THEN
      CONTINUE;
    END IF;

    FOR _policy IN
      SELECT p.policyname
      FROM pg_policies p
      WHERE p.schemaname = 'public'
        AND p.tablename = _table
    LOOP
      EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', _policy, _table);
    END LOOP;
  END LOOP;
END $$;

-- ============================================================================
-- PORTES
-- ============================================================================
DO $$
BEGIN
  IF to_regclass('public.portes') IS NULL THEN
    RETURN;
  END IF;

  ALTER TABLE public.portes ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.portes FORCE ROW LEVEL SECURITY;

  CREATE POLICY portes_select_consolidated
    ON public.portes
    FOR SELECT
    TO authenticated
    USING (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );

  CREATE POLICY portes_insert_consolidated
    ON public.portes
    FOR INSERT
    TO authenticated
    WITH CHECK (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );

  CREATE POLICY portes_update_consolidated
    ON public.portes
    FOR UPDATE
    TO authenticated
    USING (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    )
    WITH CHECK (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );

  CREATE POLICY portes_delete_consolidated
    ON public.portes
    FOR DELETE
    TO authenticated
    USING (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );
END $$;

-- ============================================================================
-- FACTORES_EMISION
-- ============================================================================
DO $$
BEGIN
  IF to_regclass('public.factores_emision') IS NULL THEN
    RETURN;
  END IF;

  ALTER TABLE public.factores_emision ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.factores_emision FORCE ROW LEVEL SECURITY;

  CREATE POLICY factores_emision_select_consolidated
    ON public.factores_emision
    FOR SELECT
    TO authenticated
    USING (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );

  CREATE POLICY factores_emision_write_consolidated
    ON public.factores_emision
    FOR ALL
    TO authenticated
    USING (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    )
    WITH CHECK (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );
END $$;

-- ============================================================================
-- GEO_CACHE
-- Only admin + gestor can read/write tenant cache rows.
-- ============================================================================
DO $$
BEGIN
  IF to_regclass('public.geo_cache') IS NULL THEN
    RETURN;
  END IF;

  ALTER TABLE public.geo_cache ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.geo_cache FORCE ROW LEVEL SECURITY;

  CREATE POLICY geo_cache_select_consolidated
    ON public.geo_cache
    FOR SELECT
    TO authenticated
    USING (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );

  CREATE POLICY geo_cache_write_consolidated
    ON public.geo_cache
    FOR ALL
    TO authenticated
    USING (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    )
    WITH CHECK (
      empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
      AND public.jwt_role() IN ('admin', 'gestor')
    );
END $$;

-- ============================================================================
-- PROFILES
-- Users can only read/update their own profile in their JWT tenant.
-- ============================================================================
DO $$
BEGIN
  IF to_regclass('public.profiles') IS NULL THEN
    RETURN;
  END IF;

  ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.profiles FORCE ROW LEVEL SECURITY;

  CREATE POLICY profiles_select_consolidated
    ON public.profiles
    FOR SELECT
    TO authenticated
    USING (
      id = auth.uid()
      AND empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
    );

  CREATE POLICY profiles_update_consolidated
    ON public.profiles
    FOR UPDATE
    TO authenticated
    USING (
      id = auth.uid()
      AND empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
    )
    WITH CHECK (
      id = auth.uid()
      AND empresa_id = (auth.jwt() ->> 'empresa_id')::uuid
    );
END $$;
