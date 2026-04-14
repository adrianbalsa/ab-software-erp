-- Stripe Billing: cliente, suscripción y límites explícitos por empresa.
ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS plan_type text;

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS limite_vehiculos integer;

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS stripe_customer_id text;

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS stripe_subscription_id text;

COMMENT ON COLUMN public.empresas.plan_type IS
  'Plan SaaS (starter|pro|enterprise|free); alineado con Stripe; si NULL se usa plan';
COMMENT ON COLUMN public.empresas.limite_vehiculos IS
  'Tope de vehículos; NULL = ilimitado (Enterprise)';
COMMENT ON COLUMN public.empresas.stripe_customer_id IS 'cus_… (Stripe Customer)';
COMMENT ON COLUMN public.empresas.stripe_subscription_id IS 'sub_… (Stripe Subscription)';

UPDATE public.empresas
SET plan_type = COALESCE(plan_type, plan)
WHERE plan_type IS NULL AND plan IS NOT NULL;
