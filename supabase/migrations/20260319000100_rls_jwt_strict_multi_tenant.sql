-- Endurecimiento RLS multi-tenant por JWT (empresa_id) para tablas críticas.
-- Política objetivo:
--   USING (auth.jwt() ->> 'empresa_id' = empresa_id::text)
-- y WITH CHECK equivalente para escrituras.

DO $$
BEGIN
  -- CLIENTES
  IF to_regclass('public.clientes') IS NOT NULL THEN
    ALTER TABLE public.clientes ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS "Read own empresa" ON public.clientes;
    DROP POLICY IF EXISTS "Write own empresa" ON public.clientes;
    DROP POLICY IF EXISTS "aislamiento_clientes" ON public.clientes;
    DROP POLICY IF EXISTS "rls_clientes" ON public.clientes;
    DROP POLICY IF EXISTS "tenant_isolation_clientes" ON public.clientes;
    DROP POLICY IF EXISTS clientes_tenant_jwt_all ON public.clientes;

    CREATE POLICY clientes_tenant_jwt_all
      ON public.clientes
      FOR ALL
      TO authenticated
      USING ((auth.jwt() ->> 'empresa_id') = empresa_id::text)
      WITH CHECK ((auth.jwt() ->> 'empresa_id') = empresa_id::text);
  END IF;

  -- PORTES
  IF to_regclass('public.portes') IS NOT NULL THEN
    ALTER TABLE public.portes ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS "Acceso total por empresa_id" ON public.portes;
    DROP POLICY IF EXISTS "Usuarios crean portes para su empresa" ON public.portes;
    DROP POLICY IF EXISTS "Usuarios ven portes de su empresa" ON public.portes;
    DROP POLICY IF EXISTS "tenant_isolation_policy_portes" ON public.portes;
    DROP POLICY IF EXISTS portes_tenant_jwt_all ON public.portes;

    CREATE POLICY portes_tenant_jwt_all
      ON public.portes
      FOR ALL
      TO authenticated
      USING ((auth.jwt() ->> 'empresa_id') = empresa_id::text)
      WITH CHECK ((auth.jwt() ->> 'empresa_id') = empresa_id::text);
  END IF;

  -- FACTURAS
  IF to_regclass('public.facturas') IS NOT NULL THEN
    ALTER TABLE public.facturas ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS "Empresas solo ven sus propias facturas" ON public.facturas;
    DROP POLICY IF EXISTS "Read own empresa" ON public.facturas;
    DROP POLICY IF EXISTS "Write own empresa" ON public.facturas;
    DROP POLICY IF EXISTS "crear_facturas_propias" ON public.facturas;
    DROP POLICY IF EXISTS "ver_facturas_propias" ON public.facturas;
    DROP POLICY IF EXISTS "rls_facturas" ON public.facturas;
    DROP POLICY IF EXISTS "tenant_isolation_policy_facturas" ON public.facturas;
    DROP POLICY IF EXISTS facturas_tenant_jwt_all ON public.facturas;

    CREATE POLICY facturas_tenant_jwt_all
      ON public.facturas
      FOR ALL
      TO authenticated
      USING ((auth.jwt() ->> 'empresa_id') = empresa_id::text)
      WITH CHECK ((auth.jwt() ->> 'empresa_id') = empresa_id::text);
  END IF;

  -- VEHICULOS
  IF to_regclass('public.vehiculos') IS NOT NULL THEN
    ALTER TABLE public.vehiculos ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS "Acceso por empresa en vehiculos" ON public.vehiculos;
    DROP POLICY IF EXISTS "tenant_isolation_policy_vehiculos" ON public.vehiculos;
    DROP POLICY IF EXISTS vehiculos_tenant_jwt_all ON public.vehiculos;

    CREATE POLICY vehiculos_tenant_jwt_all
      ON public.vehiculos
      FOR ALL
      TO authenticated
      USING ((auth.jwt() ->> 'empresa_id') = empresa_id::text)
      WITH CHECK ((auth.jwt() ->> 'empresa_id') = empresa_id::text);
  END IF;

  -- GASTOS_VEHICULO
  IF to_regclass('public.gastos_vehiculo') IS NOT NULL THEN
    ALTER TABLE public.gastos_vehiculo ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS gastos_vehiculo_tenant_all ON public.gastos_vehiculo;
    DROP POLICY IF EXISTS gastos_vehiculo_tenant_jwt_all ON public.gastos_vehiculo;

    CREATE POLICY gastos_vehiculo_tenant_jwt_all
      ON public.gastos_vehiculo
      FOR ALL
      TO authenticated
      USING ((auth.jwt() ->> 'empresa_id') = empresa_id::text)
      WITH CHECK ((auth.jwt() ->> 'empresa_id') = empresa_id::text);
  END IF;
END $$;
