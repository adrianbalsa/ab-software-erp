ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS gocardless_customer_id text,
  ADD COLUMN IF NOT EXISTS gocardless_mandate_id text;

COMMENT ON COLUMN public.empresas.gocardless_customer_id IS
  'Customer ID de GoCardless asociado a la empresa (cobros SEPA enterprise).';

COMMENT ON COLUMN public.empresas.gocardless_mandate_id IS
  'Mandate ID activo de GoCardless para cobros SEPA enterprise.';
