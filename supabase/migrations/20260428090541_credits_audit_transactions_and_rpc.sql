-- Auditoría y persistencia de créditos multi-tenant.

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS credit_balance integer NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS public.credit_transactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.empresas(id) ON DELETE CASCADE,
  amount integer NOT NULL CHECK (amount > 0),
  type text NOT NULL CHECK (type IN ('TOPUP', 'USAGE', 'SYNC')),
  description text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_credit_transactions_tenant_created
  ON public.credit_transactions (tenant_id, created_at DESC);

ALTER TABLE public.credit_transactions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS credit_transactions_tenant_read ON public.credit_transactions;
CREATE POLICY credit_transactions_tenant_read
  ON public.credit_transactions
  FOR SELECT
  TO authenticated
  USING (tenant_id::text = public.app_current_empresa_id()::text);

DROP POLICY IF EXISTS credit_transactions_tenant_insert_service ON public.credit_transactions;
CREATE POLICY credit_transactions_tenant_insert_service
  ON public.credit_transactions
  FOR INSERT
  TO authenticated
  WITH CHECK (
    (
      current_setting('request.jwt.claim.role', true) = 'service_role'
    )
    OR tenant_id::text = public.app_current_empresa_id()::text
  );

CREATE OR REPLACE FUNCTION public.record_tenant_credit_usage(
  p_empresa_id uuid,
  p_units integer,
  p_type text DEFAULT 'USAGE',
  p_description text DEFAULT NULL
)
RETURNS TABLE (
  empresa_id uuid,
  transaction_id uuid,
  balance_after integer
)
LANGUAGE plpgsql
VOLATILE
AS $$
DECLARE
  v_current_empresa text;
  v_role text;
  v_tx_type text;
  v_delta integer;
  v_balance integer;
  v_tx_id uuid;
BEGIN
  IF p_units IS NULL OR p_units <= 0 THEN
    RAISE EXCEPTION 'p_units must be positive' USING ERRCODE = '22023';
  END IF;

  v_tx_type := upper(trim(coalesce(p_type, 'USAGE')));
  IF v_tx_type NOT IN ('TOPUP', 'USAGE', 'SYNC') THEN
    RAISE EXCEPTION 'invalid transaction type' USING ERRCODE = '22023';
  END IF;

  v_role := coalesce(current_setting('request.jwt.claim.role', true), '');
  v_current_empresa := public.app_current_empresa_id()::text;
  IF v_role <> 'service_role' THEN
    IF v_current_empresa IS NULL OR p_empresa_id::text <> v_current_empresa THEN
      RAISE EXCEPTION 'tenant context mismatch' USING ERRCODE = '42501';
    END IF;
  END IF;

  v_delta := CASE WHEN v_tx_type = 'TOPUP' THEN p_units ELSE -p_units END;

  UPDATE public.empresas
  SET credit_balance = GREATEST(0, credit_balance + v_delta)
  WHERE id = p_empresa_id
  RETURNING credit_balance INTO v_balance;

  IF v_balance IS NULL THEN
    RAISE EXCEPTION 'empresa not found' USING ERRCODE = '23503';
  END IF;

  INSERT INTO public.credit_transactions(tenant_id, amount, type, description)
  VALUES (p_empresa_id, p_units, v_tx_type, p_description)
  RETURNING id INTO v_tx_id;

  RETURN QUERY
  SELECT p_empresa_id, v_tx_id, v_balance;
END;
$$;

COMMENT ON FUNCTION public.record_tenant_credit_usage(uuid, integer, text, text) IS
  'Actualiza balance de créditos del tenant e inserta transacción auditable (TOPUP/USAGE/SYNC).';

GRANT EXECUTE ON FUNCTION public.record_tenant_credit_usage(uuid, integer, text, text) TO authenticated;
