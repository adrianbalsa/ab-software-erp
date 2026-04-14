-- Webhooks salientes (integración con sistemas del cliente) + índices.
-- Ejecutar tras existir public.empresas.

CREATE TABLE IF NOT EXISTS public.webhook_endpoints (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas(id) ON DELETE CASCADE,
  url text NOT NULL,
  secret text NOT NULL,
  events text[] NOT NULL DEFAULT '{}',
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_webhook_endpoints_empresa_active
  ON public.webhook_endpoints (empresa_id)
  WHERE active = true;

CREATE TABLE IF NOT EXISTS public.webhook_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas(id) ON DELETE CASCADE,
  webhook_endpoint_id uuid REFERENCES public.webhook_endpoints(id) ON DELETE SET NULL,
  event_type text NOT NULL,
  payload jsonb NOT NULL,
  request_body text,
  response_status int,
  attempts int NOT NULL DEFAULT 0,
  failed_attempts int NOT NULL DEFAULT 0,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_webhook_logs_empresa_created
  ON public.webhook_logs (empresa_id, created_at DESC);

ALTER TABLE public.webhook_endpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.webhook_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS webhook_endpoints_tenant_all ON public.webhook_endpoints;
CREATE POLICY webhook_endpoints_tenant_all ON public.webhook_endpoints
  FOR ALL
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);

DROP POLICY IF EXISTS webhook_logs_tenant_all ON public.webhook_logs;
CREATE POLICY webhook_logs_tenant_all ON public.webhook_logs
  FOR ALL
  USING (empresa_id::text = public.app_current_empresa_id()::text)
  WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
