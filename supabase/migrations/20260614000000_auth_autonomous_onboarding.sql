-- Onboarding autónomo inicial: crea empresa + enlaza perfil autenticado.
-- Seguridad:
--   - Solo permite el "primer enlace" cuando profiles.empresa_id IS NULL.
--   - El cambio posterior de empresa_id sigue bloqueado por trigger de seguridad.

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
    activa
  )
  VALUES (
    trim(coalesce(p_cif, '')),
    trim(coalesce(p_company_name, '')),
    trim(coalesce(p_company_name, '')),
    trim(coalesce(p_address, '')),
    'starter',
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
    -- Semilla opcional: placeholder para estrategias de factores por empresa.
    PERFORM 1;
  END IF;

  RETURN QUERY
  SELECT v_empresa_id, v_uid, 'admin'::text;
END;
$$;

GRANT EXECUTE ON FUNCTION public.auth_onboarding_setup(text, text, text, text, numeric) TO authenticated;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'profiles'
  ) THEN
    DROP POLICY IF EXISTS profiles_update_authenticated ON public.profiles;
    CREATE POLICY profiles_update_authenticated ON public.profiles
      FOR UPDATE
      TO authenticated
      USING (auth.uid() = id AND empresa_id IS NULL)
      WITH CHECK (auth.uid() = id AND empresa_id IS NOT NULL);
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.profiles_block_empresa_id_escalation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  jwt jsonb;
  is_superadmin boolean;
BEGIN
  IF TG_OP <> 'UPDATE' THEN
    RETURN NEW;
  END IF;

  IF NEW.empresa_id IS NOT DISTINCT FROM OLD.empresa_id THEN
    RETURN NEW;
  END IF;

  -- Primer onboarding del propio usuario autenticado.
  IF OLD.empresa_id IS NULL
     AND NEW.empresa_id IS NOT NULL
     AND auth.uid() = OLD.id THEN
    RETURN NEW;
  END IF;

  IF current_setting('role', true) = 'service_role' THEN
    RETURN NEW;
  END IF;

  BEGIN
    jwt := auth.jwt();
  EXCEPTION WHEN OTHERS THEN
    jwt := NULL;
  END;

  is_superadmin := coalesce((jwt -> 'app_metadata' ->> 'is_superadmin')::boolean, false)
    OR lower(coalesce(jwt -> 'app_metadata' ->> 'role', '')) = 'superadmin';

  IF is_superadmin THEN
    RETURN NEW;
  END IF;

  RAISE EXCEPTION
    'SECURITY: empresa_id en profiles no es editable para este rol. Use service_role o app_metadata.is_superadmin.';
END;
$$;
