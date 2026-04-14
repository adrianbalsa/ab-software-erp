-- =============================================================================
-- Pista de auditoría inmutable: public.process_audit_log() + triggers
-- (facturas, portes, gastos, bank_transactions) + RPC audit_logs_insert_api_event
-- para inserciones desde la API con JWT. SELECT: solo owner del tenant activo.
-- =============================================================================

ALTER TYPE public.audit_action ADD VALUE IF NOT EXISTS 'INVITE_RESENT';

BEGIN;

-- Columnas opcionales (compat 20260438)
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS tabla_afectada text;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS operacion text;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS registro_id uuid;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS usuario_id uuid;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS fecha timestamptz;

-- ─── 1) Quitar triggers que dependen de las funciones antiguas ───────────────
DO $drop_trg$
BEGIN
  IF to_regclass('public.facturas') IS NOT NULL THEN
    EXECUTE 'DROP TRIGGER IF EXISTS trg_audit_row_facturas ON public.facturas';
  END IF;
  IF to_regclass('public.portes') IS NOT NULL THEN
    EXECUTE 'DROP TRIGGER IF EXISTS trg_audit_row_portes ON public.portes';
  END IF;
  IF to_regclass('public.gastos') IS NOT NULL THEN
    EXECUTE 'DROP TRIGGER IF EXISTS trg_audit_row_gastos ON public.gastos';
  END IF;
  IF to_regclass('public.bank_transactions') IS NOT NULL THEN
    EXECUTE 'DROP TRIGGER IF EXISTS trg_audit_row_bank_transactions ON public.bank_transactions';
  END IF;
END
$drop_trg$;

DROP FUNCTION IF EXISTS public.log_table_changes() CASCADE;
DROP FUNCTION IF EXISTS public.audit_row_change() CASCADE;

-- ─── 2) Función trigger canónica ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.process_audit_log()
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
  v_action public.audit_action;
  v_role text;
BEGIN
  v_role := public.app_rbac_role();

  IF TG_OP = 'INSERT' THEN
    v_action := 'INSERT'::public.audit_action;
    v_old := NULL;
    v_new := to_jsonb(NEW);
    v_empresa := COALESCE(
      NULLIF(trim(public.app_current_empresa_id()::text), '')::uuid,
      (NEW).empresa_id
    );
  ELSIF TG_OP = 'UPDATE' THEN
    v_action := 'UPDATE'::public.audit_action;
    v_old := to_jsonb(OLD);
    v_new := to_jsonb(NEW);
    v_empresa := COALESCE(
      NULLIF(trim(public.app_current_empresa_id()::text), '')::uuid,
      (NEW).empresa_id,
      (OLD).empresa_id
    );
  ELSIF TG_OP = 'DELETE' THEN
    v_action := 'DELETE'::public.audit_action;
    v_old := to_jsonb(OLD);
    v_new := NULL;
    v_empresa := COALESCE(
      NULLIF(trim(public.app_current_empresa_id()::text), '')::uuid,
      (OLD).empresa_id
    );
  ELSE
    RETURN COALESCE(NEW, OLD);
  END IF;

  IF v_new IS NOT NULL THEN
    v_new := jsonb_set(
      v_new,
      '{_audit_role}',
      to_jsonb(v_role),
      true
    );
  END IF;

  v_record_id_text := COALESCE(v_new ->> 'id', v_old ->> 'id');
  IF v_record_id_text IS NULL OR length(trim(v_record_id_text)) = 0 THEN
    v_record_id_text := gen_random_uuid()::text;
    v_record_id := NULL;
  ELSE
    BEGIN
      v_record_id := trim(v_record_id_text)::uuid;
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
    v_record_id_text,
    v_action,
    v_old,
    v_new,
    auth.uid(),
    TG_TABLE_NAME::text,
    TG_OP::text,
    v_record_id,
    auth.uid(),
    now()
  );

  RETURN COALESCE(NEW, OLD);
END;
$$;

COMMENT ON FUNCTION public.process_audit_log() IS
  'Trigger AFTER INSERT/UPDATE/DELETE: OLD/NEW → public.audit_logs (SECURITY DEFINER).';

-- ─── 3) Re-enganchar triggers ────────────────────────────────────────────────
DO $attach$
BEGIN
  IF to_regclass('public.facturas') IS NOT NULL THEN
    EXECUTE 'CREATE TRIGGER trg_audit_row_facturas AFTER INSERT OR UPDATE OR DELETE ON public.facturas FOR EACH ROW EXECUTE PROCEDURE public.process_audit_log()';
  END IF;
  IF to_regclass('public.portes') IS NOT NULL THEN
    EXECUTE 'CREATE TRIGGER trg_audit_row_portes AFTER INSERT OR UPDATE OR DELETE ON public.portes FOR EACH ROW EXECUTE PROCEDURE public.process_audit_log()';
  END IF;
  IF to_regclass('public.gastos') IS NOT NULL THEN
    EXECUTE 'CREATE TRIGGER trg_audit_row_gastos AFTER INSERT OR UPDATE OR DELETE ON public.gastos FOR EACH ROW EXECUTE PROCEDURE public.process_audit_log()';
  END IF;
  IF to_regclass('public.bank_transactions') IS NOT NULL THEN
    EXECUTE 'CREATE TRIGGER trg_audit_row_bank_transactions AFTER INSERT OR UPDATE OR DELETE ON public.bank_transactions FOR EACH ROW EXECUTE PROCEDURE public.process_audit_log()';
  END IF;
END
$attach$;

-- ─── 4) RPC: append desde API (JWT) ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.audit_logs_insert_api_event(
  p_empresa_id uuid,
  p_table_name text,
  p_record_id text,
  p_action text,
  p_old_data jsonb DEFAULT NULL,
  p_new_data jsonb DEFAULT NULL,
  p_changed_by uuid DEFAULT NULL
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id uuid;
  v_uid uuid;
  v_rec text;
  v_reg uuid;
  v_action public.audit_action;
  v_ok boolean;
BEGIN
  v_uid := auth.uid();
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'audit_logs_insert_api_event: auth.uid() requerido';
  END IF;

  v_ok := false;
  IF to_regclass('public.profiles') IS NOT NULL THEN
    SELECT EXISTS (
      SELECT 1
      FROM public.profiles p
      WHERE p.id = v_uid
        AND p.empresa_id = p_empresa_id
    ) INTO v_ok;
  END IF;

  IF NOT v_ok AND to_regclass('public.usuarios') IS NOT NULL THEN
    SELECT EXISTS (
      SELECT 1
      FROM public.usuarios u
      WHERE u.id::text = v_uid::text
        AND u.empresa_id = p_empresa_id
    ) INTO v_ok;
  END IF;

  IF NOT v_ok THEN
    RAISE EXCEPTION 'audit_logs_insert_api_event: usuario no pertenece a la empresa indicada';
  END IF;

  v_rec := NULLIF(trim(p_record_id), '');
  IF v_rec IS NULL OR length(v_rec) = 0 THEN
    v_rec := gen_random_uuid()::text;
    v_reg := NULL;
  ELSE
    BEGIN
      v_reg := v_rec::uuid;
    EXCEPTION
      WHEN others THEN
        v_reg := NULL;
    END;
  END IF;

  BEGIN
    v_action := upper(trim(p_action))::public.audit_action;
  EXCEPTION
    WHEN others THEN
      RAISE EXCEPTION 'audit_logs_insert_api_event: acción no válida: %', p_action;
  END;

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
    p_empresa_id,
    left(trim(p_table_name), 128),
    v_rec,
    v_action,
    p_old_data,
    p_new_data,
    COALESCE(p_changed_by, v_uid),
    left(trim(p_table_name), 128),
    upper(trim(p_action)),
    v_reg,
    COALESCE(p_changed_by, v_uid),
    now()
  )
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

COMMENT ON FUNCTION public.audit_logs_insert_api_event IS
  'Append-only vía API: valida pertenencia a empresa; devuelve id del log.';

REVOKE INSERT ON TABLE public.audit_logs FROM PUBLIC;
REVOKE INSERT ON TABLE public.audit_logs FROM authenticated;
REVOKE INSERT ON TABLE public.audit_logs FROM anon;

GRANT INSERT ON TABLE public.audit_logs TO service_role;

GRANT EXECUTE ON FUNCTION public.audit_logs_insert_api_event(
  uuid, text, text, text, jsonb, jsonb, uuid
) TO authenticated;

-- ─── 5) RLS: SELECT solo owner ───────────────────────────────────────────────
DROP POLICY IF EXISTS audit_logs_select_tenant ON public.audit_logs;
DROP POLICY IF EXISTS audit_logs_select_tenant_admin ON public.audit_logs;
DROP POLICY IF EXISTS audit_logs_select_admin_only ON public.audit_logs;

CREATE POLICY audit_logs_select_owner_tenant ON public.audit_logs
  FOR SELECT
  USING (
    public.app_current_empresa_id()::text IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'owner'
  );

CREATE INDEX IF NOT EXISTS idx_audit_logs_empresa_table_record_created
  ON public.audit_logs (empresa_id, table_name, record_id, created_at DESC);

COMMIT;
