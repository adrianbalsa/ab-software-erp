-- =============================================================================
-- Audit logs pasivos (triggers) — portes, facturas, gastos
-- Captura INSERT/UPDATE/DELETE sin tocar la API FastAPI.
-- auth.uid() rellena changed_by cuando la mutación llega con JWT de usuario;
-- con service_role suele ser NULL (acción de sistema / backend).
-- =============================================================================

CREATE TYPE public.audit_action AS ENUM ('INSERT', 'UPDATE', 'DELETE');

CREATE TABLE IF NOT EXISTS public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL,
  table_name varchar(128) NOT NULL,
  record_id text NOT NULL,
  action public.audit_action NOT NULL,
  old_data jsonb,
  new_data jsonb,
  changed_by uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_empresa_created
  ON public.audit_logs (empresa_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_logs_table_record
  ON public.audit_logs (table_name, record_id);

COMMENT ON TABLE public.audit_logs IS
  'Trazabilidad de cambios en tablas críticas (triggers). record_id en texto para cualquier tipo de PK.';
COMMENT ON COLUMN public.audit_logs.record_id IS
  'Valor textual de la PK de la fila afectada (UUID u otro).';
COMMENT ON COLUMN public.audit_logs.changed_by IS
  'auth.users.id cuando existe contexto JWT; NULL en escrituras con service_role u operaciones de sistema.';

-- ─── Función genérica de auditoría ───────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.audit_row_change()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_empresa uuid;
  v_old jsonb;
  v_new jsonb;
  v_record_id text;
  v_action public.audit_action;
BEGIN
  IF TG_OP = 'INSERT' THEN
    v_action := 'INSERT';
    v_old := NULL;
    v_new := to_jsonb(NEW);
    v_empresa := NEW.empresa_id;
  ELSIF TG_OP = 'UPDATE' THEN
    v_action := 'UPDATE';
    v_old := to_jsonb(OLD);
    v_new := to_jsonb(NEW);
    v_empresa := NEW.empresa_id;
  ELSIF TG_OP = 'DELETE' THEN
    v_action := 'DELETE';
    v_old := to_jsonb(OLD);
    v_new := NULL;
    v_empresa := OLD.empresa_id;
  ELSE
    RETURN COALESCE(NEW, OLD);
  END IF;

  v_record_id := coalesce(v_new->>'id', v_old->>'id');
  IF v_record_id IS NULL OR length(trim(v_record_id)) = 0 THEN
    v_record_id := gen_random_uuid()::text;
  END IF;

  INSERT INTO public.audit_logs (
    empresa_id,
    table_name,
    record_id,
    action,
    old_data,
    new_data,
    changed_by
  ) VALUES (
    v_empresa,
    TG_TABLE_NAME::varchar(128),
    v_record_id,
    v_action,
    v_old,
    v_new,
    auth.uid()
  );

  RETURN COALESCE(NEW, OLD);
END;
$$;

COMMENT ON FUNCTION public.audit_row_change() IS
  'Trigger genérico AFTER INSERT/UPDATE/DELETE → public.audit_logs.';

-- ─── Triggers en tablas críticas ─────────────────────────────────────────────

DROP TRIGGER IF EXISTS trg_audit_row_portes ON public.portes;
CREATE TRIGGER trg_audit_row_portes
  AFTER INSERT OR UPDATE OR DELETE ON public.portes
  FOR EACH ROW
  EXECUTE PROCEDURE public.audit_row_change();

DROP TRIGGER IF EXISTS trg_audit_row_facturas ON public.facturas;
CREATE TRIGGER trg_audit_row_facturas
  AFTER INSERT OR UPDATE OR DELETE ON public.facturas
  FOR EACH ROW
  EXECUTE PROCEDURE public.audit_row_change();

DROP TRIGGER IF EXISTS trg_audit_row_gastos ON public.gastos;
CREATE TRIGGER trg_audit_row_gastos
  AFTER INSERT OR UPDATE OR DELETE ON public.gastos
  FOR EACH ROW
  EXECUTE PROCEDURE public.audit_row_change();

-- ─── RLS: lectura por tenant (misma sesión que set_empresa_context) ─────────

ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS audit_logs_select_tenant ON public.audit_logs;
CREATE POLICY audit_logs_select_tenant ON public.audit_logs
  FOR SELECT
  USING (
    public.app_current_empresa_id()::text IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
  );

-- Sin política INSERT/UPDATE/DELETE para roles autenticados: solo el trigger (SECURITY DEFINER) escribe.

GRANT SELECT ON public.audit_logs TO authenticated;
GRANT SELECT ON public.audit_logs TO service_role;
