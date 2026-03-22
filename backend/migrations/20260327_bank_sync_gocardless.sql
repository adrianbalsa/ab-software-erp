-- GoCardless Bank Account Data: vínculo por empresa (tokens cifrados en aplicación).
-- Columnas de cobro en facturas para conciliación automática.

CREATE TABLE IF NOT EXISTS public.empresa_banco_sync (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  requisition_id_enc TEXT NOT NULL,
  access_token_enc TEXT,
  institution_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT empresa_banco_sync_empresa_unique UNIQUE (empresa_id)
);

COMMENT ON TABLE public.empresa_banco_sync IS
  'GoCardless (Nordigen): requisition_id y access JWT cifrados por la API antes de persistir.';
COMMENT ON COLUMN public.empresa_banco_sync.requisition_id_enc IS 'Fernet ciphertext (base64) del requisition UUID';
COMMENT ON COLUMN public.empresa_banco_sync.access_token_enc IS 'Fernet ciphertext del último access JWT de Bank Account Data';

CREATE INDEX IF NOT EXISTS idx_empresa_banco_sync_empresa ON public.empresa_banco_sync (empresa_id);

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS estado_cobro TEXT NOT NULL DEFAULT 'emitida',
  ADD COLUMN IF NOT EXISTS pago_id TEXT;

COMMENT ON COLUMN public.facturas.estado_cobro IS 'emitida | cobrada';
COMMENT ON COLUMN public.facturas.pago_id IS 'ID movimiento bancario (GoCardless transactionId u otro ref.)';

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'empresa_banco_sync'
  ) THEN
    ALTER TABLE public.empresa_banco_sync ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS empresa_banco_sync_tenant_all ON public.empresa_banco_sync;
    CREATE POLICY empresa_banco_sync_tenant_all ON public.empresa_banco_sync
      FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id())
      WITH CHECK (empresa_id::text = public.app_current_empresa_id());
  END IF;
END $$;
