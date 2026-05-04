-- Self-serve: empresas creadas vía onboarding autónomo deben completar Stripe Checkout
-- antes de mutar datos operativos (API: ``assert_empresa_billing_active`` + ``bind_write_context``).
-- Legacy: ``requires_stripe_subscription = false`` por defecto en filas existentes.

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS requires_stripe_subscription boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.empresas.requires_stripe_subscription IS
  'Si true y Stripe está configurado, exige suscripción activa (checkout) salvo excepciones de desarrollo.';

CREATE OR REPLACE FUNCTION public.auth_onboarding_setup(
  p_company_name text,
  p_cif text,
  p_address text,
  p_initial_fleet_type text,
  p_target_margin_pct numeric DEFAULT NULL
)
RETURNS TABLE (empresa_id uuid, profile_id uuid, role text)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
  v_uid uuid;
  v_empresa_id uuid;
BEGIN
  v_uid := auth.uid();
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'auth_uid_missing';
  END IF;

  PERFORM 1
  FROM public.profiles p
  WHERE p.id = v_uid
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'profile_not_found';
  END IF;

  PERFORM 1
  FROM public.profiles p
  WHERE p.id = v_uid
    AND p.empresa_id IS NOT NULL;

  IF FOUND THEN
    RAISE EXCEPTION 'already_onboarded';
  END IF;

  INSERT INTO public.empresas (
    nif,
    nombre_legal,
    nombre_comercial,
    direccion,
    plan,
    plan_type,
    activa,
    requires_stripe_subscription
  )
  VALUES (
    trim(coalesce(p_cif, '')),
    trim(coalesce(p_company_name, '')),
    trim(coalesce(p_company_name, '')),
    trim(coalesce(p_address, '')),
    'starter',
    'starter',
    true,
    true
  )
  RETURNING id INTO v_empresa_id;

  UPDATE public.profiles
  SET
    empresa_id = v_empresa_id,
    role = 'admin'::public.user_role,
    rol = 'admin'
  WHERE id = v_uid
    AND empresa_id IS NULL;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'already_onboarded';
  END IF;

  IF to_regclass('public.factores_emision') IS NOT NULL THEN
    PERFORM 1;
  END IF;

  RETURN QUERY
  SELECT v_empresa_id, v_uid, 'admin'::text;
END;
$$;

GRANT EXECUTE ON FUNCTION public.auth_onboarding_setup(text, text, text, text, numeric) TO authenticated;
