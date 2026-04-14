-- Mirror of supabase/migrations/20260413_bank_accounts_transactions_open_banking.sql

CREATE TABLE IF NOT EXISTS public.bank_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  gocardless_account_id TEXT NOT NULL,
  institution_id TEXT,
  iban_masked TEXT,
  currency TEXT NOT NULL DEFAULT 'EUR',
  status TEXT NOT NULL DEFAULT 'linked',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT bank_accounts_empresa_gc_account UNIQUE (empresa_id, gocardless_account_id)
);

COMMENT ON TABLE public.bank_accounts IS
  'Cuentas bancarias enlazadas vía GoCardless Bank Account Data (Nordigen); un registro por account_id de la API.';

CREATE INDEX IF NOT EXISTS idx_bank_accounts_empresa ON public.bank_accounts (empresa_id);

ALTER TABLE public.bank_transactions
  ADD COLUMN IF NOT EXISTS bank_account_id UUID REFERENCES public.bank_accounts (id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS gocardless_account_id TEXT,
  ADD COLUMN IF NOT EXISTS remittance_info TEXT,
  ADD COLUMN IF NOT EXISTS internal_status TEXT NOT NULL DEFAULT 'imported';

CREATE INDEX IF NOT EXISTS idx_bank_transactions_gc_account ON public.bank_transactions (empresa_id, gocardless_account_id);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'bank_accounts'
  ) THEN
    ALTER TABLE public.bank_accounts ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS bank_accounts_tenant_all ON public.bank_accounts;
    CREATE POLICY bank_accounts_tenant_all ON public.bank_accounts
      FOR ALL
      USING (empresa_id::text = public.app_current_empresa_id()::text)
      WITH CHECK (empresa_id::text = public.app_current_empresa_id()::text);
  END IF;
END $$;
