-- RLS bootstrap for tenant context on Starter/Pro projects.

CREATE OR REPLACE FUNCTION public.app_current_empresa_id()
RETURNS uuid AS $$
  SELECT NULLIF(current_setting('app.current_empresa_id', TRUE), '')::uuid;
$$ LANGUAGE sql STABLE;

DO $$
BEGIN
  IF to_regclass('public.facturas') IS NOT NULL THEN
    ALTER TABLE public.facturas ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS facturas_tenant_all ON public.facturas;
    DROP POLICY IF EXISTS facturas_select_rbac ON public.facturas;
    DROP POLICY IF EXISTS facturas_insert_rbac ON public.facturas;
    DROP POLICY IF EXISTS facturas_update_rbac ON public.facturas;
    DROP POLICY IF EXISTS facturas_delete_rbac ON public.facturas;
    CREATE POLICY facturas_tenant_all ON public.facturas
      FOR ALL
      USING (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      )
      WITH CHECK (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      );
  END IF;

  IF to_regclass('public.transacciones') IS NOT NULL THEN
    ALTER TABLE public.transacciones ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS transacciones_tenant_all ON public.transacciones;
    CREATE POLICY transacciones_tenant_all ON public.transacciones
      FOR ALL
      USING (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      )
      WITH CHECK (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      );
  END IF;

  IF to_regclass('public.movimientos_bancarios') IS NOT NULL THEN
    ALTER TABLE public.movimientos_bancarios ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS movimientos_bancarios_tenant_all ON public.movimientos_bancarios;
    CREATE POLICY movimientos_bancarios_tenant_all ON public.movimientos_bancarios
      FOR ALL
      USING (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      )
      WITH CHECK (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      );
  END IF;

  IF to_regclass('public.bank_transactions') IS NOT NULL THEN
    ALTER TABLE public.bank_transactions ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS bank_transactions_tenant_all ON public.bank_transactions;
    CREATE POLICY bank_transactions_tenant_all ON public.bank_transactions
      FOR ALL
      USING (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      )
      WITH CHECK (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      );
  END IF;

  IF to_regclass('public.audit_logs') IS NOT NULL THEN
    ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS audit_logs_select_admin_only ON public.audit_logs;
    DROP POLICY IF EXISTS audit_logs_select_tenant_admin ON public.audit_logs;
    DROP POLICY IF EXISTS audit_logs_select_tenant ON public.audit_logs;
    CREATE POLICY audit_logs_select_tenant ON public.audit_logs
      FOR SELECT
      USING (
        public.app_current_empresa_id() IS NOT NULL
        AND empresa_id = public.app_current_empresa_id()
      );
  END IF;
END
$$;
