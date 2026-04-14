-- =============================================================================
-- Audit Logs inmutable (Append-Only) + Trigger genérico seguro
-- =============================================================================
-- Objetivos:
-- 1) Append-only: bloquear completamente UPDATE y DELETE sobre public.audit_logs
-- 2) Lectura: solo administradores del tenant (owner/traffic_manager) pueden hacer SELECT
-- 3) Función public.log_table_changes() (TRIGGER) conforme al contrato pedido:
--    - Leer TG_TABLE_NAME y TG_OP
--    - Extraer empresa_id usando public.app_current_empresa_id()::text
--      y si es NULL => fallback NEW.empresa_id / OLD.empresa_id
--    - old_data con row_to_json(OLD), new_data con row_to_json(NEW)
--    - usuario_id desde auth.uid()
-- 4) Re-enganchar triggers AFTER INSERT/UPDATE/DELETE en public.facturas y public.portes
--
-- Nota: El repo ya contiene un audit_logs (20260424_audit_logs_triggers.sql).
-- Esta migración lo "endurece" sin romper el contrato existente del API actual.
-- =============================================================================

BEGIN;

-- ─── 1) Columnas nominales según especificación (compatibles con el esquema actual) ───
ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS tabla_afectada text;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS operacion text;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS registro_id uuid;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS usuario_id uuid;

ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS fecha timestamptz DEFAULT now();

-- ─── 2) RLS: lectura solo tenant-admin + bloqueo UPDATE/DELETE ───
-- SELECT: owner/traffic_manager + tenant activo (app_current_empresa_id)
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS audit_logs_select_tenant ON public.audit_logs;

CREATE POLICY audit_logs_select_tenant_admin
  ON public.audit_logs
  FOR SELECT
  USING (
    public.app_current_empresa_id()::text IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager')
  );

-- Append-only: impedir UPDATE y DELETE de forma explícita (incluso si alguien tuviera privilegios).
DROP POLICY IF EXISTS audit_logs_no_update ON public.audit_logs;
CREATE POLICY audit_logs_no_update
  ON public.audit_logs
  FOR UPDATE
  USING (false)
  WITH CHECK (false);

DROP POLICY IF EXISTS audit_logs_no_delete ON public.audit_logs;
CREATE POLICY audit_logs_no_delete
  ON public.audit_logs
  FOR DELETE
  USING (false);

-- Refuerzo de privilegios a nivel GRANT/REVOKE.
REVOKE UPDATE, DELETE ON public.audit_logs FROM PUBLIC;
REVOKE UPDATE, DELETE ON public.audit_logs FROM authenticated;
REVOKE UPDATE, DELETE ON public.audit_logs FROM anon;

-- ─── 3) Función genérica de auditoría: public.log_table_changes() ───
-- Inserta en el esquema actual (table_name/record_id/action/changed_by/created_at)
-- y además rellena las columnas nominales (tabla_afectada/operacion/registro_id/usuario_id/fecha).
CREATE OR REPLACE FUNCTION public.log_table_changes()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_empresa uuid;
  v_old jsonb;
  v_new jsonb;
  v_record_id_text text;
  v_record_id uuid;
  v_action_text text;
BEGIN
  v_action_text := TG_OP;

  -- 1) empresa_id: primero contexto de sesión, luego fallback NEW/OLD.
  v_empresa := NULLIF(public.app_current_empresa_id()::text, '')::uuid;

  IF TG_OP = 'INSERT' THEN
    v_old := NULL;
    v_new := to_jsonb(NEW);
    v_empresa := COALESCE(v_empresa, NEW.empresa_id);
  ELSIF TG_OP = 'UPDATE' THEN
    v_old := to_jsonb(OLD);
    v_new := to_jsonb(NEW);
    v_empresa := COALESCE(v_empresa, NEW.empresa_id);
  ELSIF TG_OP = 'DELETE' THEN
    v_old := to_jsonb(OLD);
    v_new := NULL;
    v_empresa := COALESCE(v_empresa, OLD.empresa_id);
  ELSE
    RETURN COALESCE(NEW, OLD);
  END IF;

  -- 2) registro_id: intentamos parsear id => uuid, y guardamos también en record_id (texto).
  v_record_id_text := COALESCE(
    (v_new ->> 'id'),
    (v_old ->> 'id')
  );

  IF v_record_id_text IS NULL OR length(trim(v_record_id_text)) = 0 THEN
    v_record_id := NULL;
  ELSE
    BEGIN
      v_record_id := v_record_id_text::uuid;
    EXCEPTION
      WHEN others THEN
        v_record_id := NULL;
    END;
  END IF;

  INSERT INTO public.audit_logs (
    empresa_id,
    table_name,
    record_id,
    action,
    old_data,
    new_data,
    changed_by,
    tabla_afectada,
    operacion,
    registro_id,
    usuario_id,
    fecha
  ) VALUES (
    v_empresa,
    TG_TABLE_NAME::varchar(128),
    COALESCE(v_record_id_text, gen_random_uuid()::text),
    v_action_text::public.audit_action,
    v_old,
    v_new,
    auth.uid(),
    TG_TABLE_NAME::text,
    v_action_text::text,
    v_record_id,
    auth.uid(),
    now()
  );

  RETURN COALESCE(NEW, OLD);
END;
$$;

COMMENT ON FUNCTION public.log_table_changes() IS
  'Trigger genérico Append-Only para audit_logs. Extrae empresa_id desde app_current_empresa_id() con fallback NEW/OLD.';

-- ─── 4) Aplicación del trigger ───
-- Facturas
DROP TRIGGER IF EXISTS trg_audit_row_facturas ON public.facturas;
CREATE TRIGGER trg_audit_row_facturas
  AFTER INSERT OR UPDATE OR DELETE ON public.facturas
  FOR EACH ROW
  EXECUTE PROCEDURE public.log_table_changes();

-- Portes
DROP TRIGGER IF EXISTS trg_audit_row_portes ON public.portes;
CREATE TRIGGER trg_audit_row_portes
  AFTER INSERT OR UPDATE OR DELETE ON public.portes
  FOR EACH ROW
  EXECUTE PROCEDURE public.log_table_changes();

COMMIT;

