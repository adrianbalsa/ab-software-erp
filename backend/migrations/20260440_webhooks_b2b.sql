-- Webhooks B2B: una fila por suscripción (empresa + event_type + URL).
-- RLS: solo rol owner (ADMIN en API) puede gestionar; el backend con service role envía.

CREATE TABLE IF NOT EXISTS public.webhooks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  event_type text NOT NULL,
  target_url text NOT NULL,
  secret_key text NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_webhooks_empresa_event_active
  ON public.webhooks (empresa_id, event_type)
  WHERE is_active = true;

ALTER TABLE public.webhooks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS webhooks_select_owner ON public.webhooks;
CREATE POLICY webhooks_select_owner ON public.webhooks
  FOR SELECT
  USING (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'owner'
  );

DROP POLICY IF EXISTS webhooks_insert_owner ON public.webhooks;
CREATE POLICY webhooks_insert_owner ON public.webhooks
  FOR INSERT
  WITH CHECK (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'owner'
  );

DROP POLICY IF EXISTS webhooks_update_owner ON public.webhooks;
CREATE POLICY webhooks_update_owner ON public.webhooks
  FOR UPDATE
  USING (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'owner'
  )
  WITH CHECK (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'owner'
  );

DROP POLICY IF EXISTS webhooks_delete_owner ON public.webhooks;
CREATE POLICY webhooks_delete_owner ON public.webhooks
  FOR DELETE
  USING (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'owner'
  );

COMMENT ON TABLE public.webhooks IS
  'Webhooks salientes B2B por evento; RLS solo owner (ADMIN).';

ALTER TABLE public.webhook_logs
  ADD COLUMN IF NOT EXISTS webhook_id uuid REFERENCES public.webhooks (id) ON DELETE SET NULL;
