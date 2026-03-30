os;
    CREATE POLICY empleados_tenant_all ON public.empleados FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'eco_registros') THEN
    ALTER TABLE public.eco_registros ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS eco_registros_tenant_all ON public.eco_registros;
    CREATE POLICY eco_registros_tenant_all ON public.eco_registros FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;

-- MANTENIMIENTO_FLOTA (si existe y tiene empresa_id)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'mantenimiento_flota' AND column_name = 'empresa_id'
  ) THEN
    ALTER TABLE public.mantenimiento_flota ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS mantenimiento_flota_tenant_all ON public.mantenimiento_flota;
    CREATE POLICY mantenimiento_flota_tenant_all ON public.mantenimiento_flota FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;


-- >>> 11_20260325_pii_widen_nif_ferrnet_columns.sql.json
-- PII encryption compatibility: Fernet tokens are longer than legacy VARCHAR limits.
-- We widen these columns to `text` so encrypted values can be persisted safely.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'empresas'
      AND column_name = 'nif'
  ) THEN
    ALTER TABLE public.empresas ALTER COLUMN nif TYPE text;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'facturas'
      AND column_name = 'nif_emisor'
  ) THEN
    ALTER TABLE public.facturas ALTER COLUMN nif_emisor TYPE text;
  END IF;
END $$;



-- >>> 12_20260325_rls_granular_profiles_empresa_id_lock.sql.json
-- =============================================================================
-- Auditoría seguridad: políticas RLS explícitas (SELECT/INSERT/UPDATE/DELETE)
-- para portes, vehículos/flota y auditoría; bloqueo de cambio de empresa_id en profiles.
-- =============================================================================
-- Requisitos: Supabase (auth.jwt(), auth.uid(), auth.role()).
-- Contexto tenant: public.app_current_empresa_id()::text (ver migración 20260324).
-- =============================================================================

-- ─── PORTES: cuatro políticas explícitas ───────────────────────────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'portes'
  ) THEN
    ALTER TABLE public.portes ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS portes_tenant_all ON public.portes;
    DROP POLICY IF EXISTS portes_select_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_insert_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_update_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_delete_tenant ON public.portes;

    CREATE POLICY portes_select_tenant ON public.portes
      FOR SELECT
      USING (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY portes_insert_tenant ON public.portes
      FOR INSERT
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY portes_update_tenant ON public.portes
      FOR UPDATE
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY portes_delete_tenant ON public.portes
      FOR DELETE
      USING (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;

-- ─── VEHÍCULOS: tabla public.vehiculos (si existe) ─────────────────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vehiculos'
  ) THEN
    ALTER TABLE public.vehiculos ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS vehiculos_tenant_all ON public.vehiculos;
    DROP POLICY IF EXISTS vehiculos_select_tenant ON public.vehiculos;
    DROP POLICY IF EXISTS vehiculos_insert_tenant ON public.vehiculos;
    DROP POLICY IF EXISTS vehiculos_update_tenant ON public.vehiculos;
    DROP POLICY IF EXISTS vehiculos_delete_tenant ON public.vehiculos;

    CREATE POLICY vehiculos_select_tenant ON public.vehiculos
      FOR SELECT
      USING (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY vehiculos_insert_tenant ON public.vehiculos
      FOR INSERT
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY vehiculos_update_tenant ON public.vehiculos
      FOR UPDATE
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

    CREATE POLICY vehiculos_delete_tenant ON public.vehiculos
      FOR DELETE
      USING (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;

-- ─── FLOTA (sinónimo operativo de “vehículos