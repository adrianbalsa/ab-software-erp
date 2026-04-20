-- Stripe Billing: estado de suscripción y flag de acceso por webhook.
ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS subscription_status text;

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN public.empresas.subscription_status IS
  'Último estado conocido de la suscripción Stripe (active, past_due, unpaid, canceled, …); NULL si sin billing.';

COMMENT ON COLUMN public.empresas.is_active IS
  'Si false, la API bloquea el tenant por facturación (p. ej. invoice.payment_failed) hasta regularizar.';
