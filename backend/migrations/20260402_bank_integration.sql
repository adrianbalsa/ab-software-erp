-- Open Banking (GoCardless): cuentas cifradas, historial de movimientos y vínculo con facturas.

-- ─── Cuenta bancaria por empresa (requisition / account IDs cifrados en aplicación como texto Fernet) ───
CREATE TABLE IF NOT EXISTS public.empresa_bank_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  requisition_id_enc TEXT NOT NULL,
  account_id_enc TEXT,
  institution_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT empresa_bank_accounts_empresa_unique UNIQUE (empresa_id)
);

COMMENT ON TABLE public.empresa_bank_accounts IS
  'GoCardless: requisition_id y account_id cifrados (Fernet) antes de persistir.';
COMMENT ON COLUMN public.empresa_bank_accounts.requisition_id_enc IS 'Ciphertext Fernet (base64) del requisition UUID';
COMMENT ON COLUMN public.empresa_bank_accounts.account_id_enc IS 'Ciphertext Fernet del account_id GoCardless (primera cuenta o selección)';

CREATE INDEX IF NOT EXISTS idx_empresa_bank_accounts_empresa ON public.empresa_bank_accounts (empresa_id);

-- Copia desde tabla legada si existe (mismos ciphertexts).
INSERT INTO public.empresa_bank_accounts (empresa_id, requisition_id_enc, institution_id, created_at, updated_at)
SELECT ebs.empresa_id, ebs.requisition_id_enc, ebs.institution_id, ebs.created_at, ebs.updated_at
FROM public.empresa_banco_sync AS ebs
ON CONFLICT (empresa_id) DO NOTHING;

-- ─── Movimientos importados (conciliación; sin PII en logs de aplicación) ───
CREATE TABLE IF NOT EXISTS public.bank_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  transaction_id TEXT NOT NULL,
  amount NUMERIC(18, 2) NOT NULL,
  booked_date DATE NOT NULL,
  currency TEXT NOT NULL DEFAULT 'EUR',
  description TEXT,
  reconciled BOOLEAN NOT NULL DEFAULT false,
  raw_fingerprint TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT bank_transactions_empresa_tx_unique UNIQUE (empresa_id, transaction_id)
);

COMMENT ON TABLE public.bank_transactions IS 'Movimientos bancarios sincronizados (GoCardless); conciliación automática opcional.';
COMMENT ON COLUMN public.bank_transactions.raw_fingerprint IS 'Hash opcional para deduplicar sin almacenar payload crudo';

CREATE INDEX IF NOT EXISTS idx_bank_transactions_empresa_booked ON public.bank_transactions (empresa_id, booked_date DESC);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_empresa_reconciled ON public.bank_transactions (empresa_id, reconciled);

-- ─── Facturas: vínculo explícito y fecha real de cobro ───
ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS matched_transaction_id TEXT,
  ADD COLUMN IF NOT EXISTS fecha_cobro_real DATE;

COMMENT ON COLUMN public.facturas.matched_transaction_id IS 'transaction_id bancario emparejado en conciliación automática';
COMMENT ON COLUMN public.facturas.fecha_cobro_real IS 'Fecha contable del cobro (p. ej. bookingDate del movimiento)';

-- ─── RLS tenant ───
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'empresa_bank_accounts'
  ) THEN
    ALTER TABLE public.empresa_bank_accounts ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS empresa_bank_accounts_tenant_all ON public.empresa_bank_accounts;
    CREATE POLICY empresa_bank_accounts_tenant_all ON public.empresa_bank_accounts
      FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id())
      WITH CHECK (empresa_id::text = public.app_current_empresa_id());
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'bank_transactions'
  ) THEN
    ALTER TABLE public.bank_transactions ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS bank_transactions_tenant_all ON public.bank_transactions;
    CREATE POLICY bank_transactions_tenant_all ON public.bank_transactions
      FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id())
      WITH CHECK (empresa_id::text = public.app_current_empresa_id());
  END IF;
END $$;
