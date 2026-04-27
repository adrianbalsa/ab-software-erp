-- VeriFactu dead-letter durable para jobs AEAT agotados.
-- No es una segunda cola: solo registra trabajos que ya consumieron todos los reintentos ARQ.

CREATE TABLE IF NOT EXISTS public.verifactu_dead_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  factura_id bigint NOT NULL REFERENCES public.facturas (id) ON DELETE RESTRICT,
  job_name text NOT NULL DEFAULT 'submit_to_aeat',
  job_try int NOT NULL,
  max_tries int NOT NULL,
  error_type text,
  error_message text,
  worker_result jsonb,
  status text NOT NULL DEFAULT 'open',
  resolved_at timestamptz,
  resolved_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT verifactu_dead_jobs_status_chk
    CHECK (status IN ('open', 'resolved', 'ignored')),
  CONSTRAINT verifactu_dead_jobs_try_chk
    CHECK (job_try >= 1 AND max_tries >= 1 AND job_try <= max_tries)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_verifactu_dead_jobs_open_unique
  ON public.verifactu_dead_jobs (factura_id, job_name)
  WHERE status = 'open';

CREATE INDEX IF NOT EXISTS idx_verifactu_dead_jobs_empresa_status_created
  ON public.verifactu_dead_jobs (empresa_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_verifactu_dead_jobs_factura_id
  ON public.verifactu_dead_jobs (factura_id);

COMMENT ON TABLE public.verifactu_dead_jobs IS
  'Dead-letter durable de jobs VeriFactu/AEAT agotados tras todos los reintentos ARQ.';
COMMENT ON COLUMN public.verifactu_dead_jobs.worker_result IS
  'Resultado parcial del worker/sender si existia al agotar reintentos; no debe contener secretos.';
COMMENT ON COLUMN public.verifactu_dead_jobs.status IS
  'open=pending operativo, resolved=reprocesado/resuelto, ignored=sin accion posterior requerida.';

ALTER TABLE public.verifactu_dead_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS verifactu_dead_jobs_select_tenant_admin
  ON public.verifactu_dead_jobs;
CREATE POLICY verifactu_dead_jobs_select_tenant_admin
  ON public.verifactu_dead_jobs
  FOR SELECT
  TO authenticated
  USING (
    public.app_current_empresa_id()::text IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager')
  );

REVOKE INSERT, UPDATE, DELETE ON public.verifactu_dead_jobs FROM PUBLIC;
REVOKE INSERT, UPDATE, DELETE ON public.verifactu_dead_jobs FROM anon;
REVOKE INSERT, UPDATE, DELETE ON public.verifactu_dead_jobs FROM authenticated;

GRANT SELECT ON public.verifactu_dead_jobs TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.verifactu_dead_jobs TO service_role;
