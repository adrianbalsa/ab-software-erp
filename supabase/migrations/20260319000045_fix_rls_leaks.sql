-- =============================================================================
-- Cierre de fugas RLS multi-tenant (SaaS B2B)
-- =============================================================================
-- 1) maps_distance_cache: la política previa permitía a cualquier rol
--    `authenticated` leer/escribir TODA la caché (USING/WITH CHECK true),
--    filtrando mal entre tenants que usan JWT + clave anon en PostgREST.
--    Se aísla por empresa_id alineado con set_empresa_context / app_current_empresa_id().
--
-- 2) clientes: maestro por tenant con empresa_id en aplicación; se fuerza RLS
--    coherente con facturas/portes.
--
-- Requisito previo: funciones public.app_current_empresa_id() y contexto de sesión
-- (ver 20260324_rls_tenant_current_empresa.sql).
--
-- NOTA: TRUNCATE en maps_distance_cache invalida entradas globales previas (solo
--       km cacheados; se regeneran vía Google API). El backend debe enviar
--       empresa_id en upsert/select (maps_service).
-- =============================================================================

-- ─── maps_distance_cache: columna tenant + índice único + política estricta ───
DO $$
BEGIN
  IF to_regclass('public.maps_distance_cache') IS NOT NULL THEN
    DROP POLICY IF EXISTS maps_distance_cache_authenticated_all ON public.maps_distance_cache;

    TRUNCATE TABLE public.maps_distance_cache;

    -- Sustituir unicidad global por unicidad por tenant
    ALTER TABLE public.maps_distance_cache
      DROP CONSTRAINT IF EXISTS maps_distance_cache_cache_key_key;

    ALTER TABLE public.maps_distance_cache
      ADD COLUMN IF NOT EXISTS empresa_id uuid REFERENCES public.empresas (id) ON DELETE CASCADE;

    -- Filas ya truncadas; exigir tenant en nuevas filas
    ALTER TABLE public.maps_distance_cache
      ALTER COLUMN empresa_id SET NOT NULL;

    CREATE UNIQUE INDEX IF NOT EXISTS uq_maps_distance_cache_empresa_cache_key
      ON public.maps_distance_cache (empresa_id, cache_key);

    ALTER TABLE public.maps_distance_cache ENABLE ROW LEVEL SECURITY;

    DROP POLICY IF EXISTS maps_distance_cache_tenant_all ON public.maps_distance_cache;
    CREATE POLICY maps_distance_cache_tenant_all ON public.maps_distance_cache
      FOR ALL
      TO authenticated
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    COMMENT ON COLUMN public.maps_distance_cache.empresa_id IS
      'Tenant propietario de la entrada de caché (aislamiento RLS).';
  ELSE
    RAISE NOTICE 'Omitido maps_distance_cache: tabla no existe';
  END IF;
END $$;

-- ─── clientes: RLS por empresa_id ───
DO $$
BEGIN
  IF to_regclass('public.clientes') IS NULL THEN
    RAISE NOTICE 'Omitido clientes: tabla no existe';
  ELSIF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'clientes' AND column_name = 'empresa_id'
  ) THEN
    RAISE NOTICE 'Omitido RLS clientes: falta columna empresa_id';
  ELSE
    ALTER TABLE public.clientes ENABLE ROW LEVEL SECURITY;

    DROP POLICY IF EXISTS clientes_tenant_all ON public.clientes;
    CREATE POLICY clientes_tenant_all ON public.clientes
      FOR ALL
      TO authenticated
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    COMMENT ON POLICY clientes_tenant_all ON public.clientes IS
      'SaaS: solo filas del tenant activo (app.current_empresa_id / app.empresa_id).';
  END IF;
END $$;
