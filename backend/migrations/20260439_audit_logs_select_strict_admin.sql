-- =============================================================================
-- Endurecer policy SELECT de audit_logs a "tenant admins" estrictos
-- (evitar fallback a owner si app.rbac_role no está seteado)
-- =============================================================================

BEGIN;

DROP POLICY IF EXISTS audit_logs_select_tenant_admin ON public.audit_logs;

CREATE POLICY audit_logs_select_tenant_admin
  ON public.audit_logs
  FOR SELECT
  USING (
    public.app_current_empresa_id()::text IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND current_setting('app.rbac_role', true) IN ('owner', 'traffic_manager')
  );

COMMIT;

