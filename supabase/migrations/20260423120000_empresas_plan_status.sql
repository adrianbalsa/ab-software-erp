-- Estado de activación del plan SaaS (webhook Stripe / portal).
ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS plan_status text;

COMMENT ON COLUMN public.empresas.plan_status IS
  'Estado comercial del plan (active, past_due, canceled, …); complementa subscription_status tras Checkout / facturas.';
