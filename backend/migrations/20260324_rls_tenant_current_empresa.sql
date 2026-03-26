-- =============================================================================
-- RLS multi-tenant: aislar filas por contexto de sesión
-- =============================================================================
-- Alineado con `set_empresa_context`: se publican **dos** claves de sesión para
-- máxima compatibilidad con código y documentación:
--   - app.empresa_id      (histórico en supabase_schema.sql)
--   - app.current_empresa_id (convención explícita solicitada)
--
-- El backend debe invocar `set_empresa_context` tras autenticación (ya implementado).
-- IMPORTANTE: El panel admin global en FastAPI suele usar la **service role** o
-- políticas que permitan lectura amplia; con JWT `anon` + RLS estricto, `/admin/*`
-- podría devolver filas vacías salvo que uses **service key** en el servidor o
-- políticas adicionales por rol. Revisa despliegue antes de activar en producción.
-- =============================================================================

-- Implementación TEXT (ids legacy no UUID).
CREATE OR REPLACE FUNCTION public.set_empresa_context(p_empresa_id text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  PERFORM set_config('app.empresa_id', p_empresa_id, true);
  PERFORM set_config('app.current_empresa_id', p_empresa_id, true);
END;
$$;

CREATE OR REPLACE FUNCTION public.set_empresa_context(p_empresa_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  PERFORM public.set_empresa_context(p_empresa_id::text);
END;
$$;

COMMENT ON FUNCTION public.set_empresa_context(text) IS
  'Establece app.empresa_id y app.current_empresa_id para políticas RLS.';

CREATE OR REPLACE FUNCTION public.app_current_empresa_id()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(
    trim(both from coalesce(
      nullif(current_setting('app.current_empresa_id', true), ''),
      nullif(current_setting('app.empresa_id', true), '')
    )),
    ''
  );
$$;

COMMENT ON FUNCTION public.app_current_empresa_id() IS
  'Tenant activo en la sesión (PostgREST/transacción). Vacío ⇒ políticas no devuelven filas.';

-- Nota: auditoria.empresa_id puede ser NULL; esas filas no serán visibles con esta política.

-- PORTES
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'portes'
  ) THEN
    ALTER TABLE public.portes ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS portes_tenant_all ON public.portes;
    CREATE POLICY portes_tenant_all ON public.portes
      FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  ELSE
    RAISE NOTICE 'Omitido RLS portes: tabla public.portes no existe';
  END IF;
END $$;

-- FACTURAS (tabla operativa VeriFactu)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'facturas'
  ) THEN
    ALTER TABLE public.facturas ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS facturas_tenant_all ON public.facturas;
    CREATE POLICY facturas_tenant_all ON public.facturas
      FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;

-- GASTOS (puede tener política previa; reemplazar)
ALTER TABLE public.gastos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS gastos_por_empresa ON public.gastos;
DROP POLICY IF EXISTS gastos_tenant_all ON public.gastos;
CREATE POLICY gastos_tenant_all ON public.gastos
  FOR ALL
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

-- FLOTA
ALTER TABLE public.flota ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS flota_tenant_all ON public.flota;
CREATE POLICY flota_tenant_all ON public.flota
  FOR ALL
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

-- AUDITORÍA (filas sin empresa_id no visibles con tenant)
ALTER TABLE public.auditoria ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS auditoria_tenant_all ON public.auditoria;
CREATE POLICY auditoria_tenant_all ON public.auditoria
  FOR ALL
  USING (
    empresa_id IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
  )
  WITH CHECK (
    empresa_id IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
  );

-- PRESUPUESTOS
ALTER TABLE public.presupuestos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS presupuestos_tenant_all ON public.presupuestos;
CREATE POLICY presupuestos_tenant_all ON public.presupuestos
  FOR ALL
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

-- INVENTARIO / EMPLEADOS / ECO (si existen)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'inventario') THEN
    ALTER TABLE public.inventario ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS inventario_tenant_all ON public.inventario;
    CREATE POLICY inventario_tenant_all ON public.inventario FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'empleados') THEN
    ALTER TABLE public.empleados ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS empleados_tenant_all ON public.empleados;
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
