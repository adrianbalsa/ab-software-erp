-- Supabase security analyzer remediations:
-- 1) Enable and enforce RLS on auth-related tables.
-- 2) Make selected views run with security_invoker.
-- 3) Lock function search_path to public.

-- ---------------------------------------------------------------------------
-- 1) RLS Disabled fixes
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = 'refresh_tokens'
      AND c.relkind = 'r'
  ) THEN
    EXECUTE 'ALTER TABLE public.refresh_tokens ENABLE ROW LEVEL SECURITY';
  END IF;
END
$$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = 'user_accounts'
      AND c.relkind = 'r'
  ) THEN
    EXECUTE 'ALTER TABLE public.user_accounts ENABLE ROW LEVEL SECURITY';
  END IF;
END
$$;

-- Owner-only access policies (auth.uid() must match user_id).
DROP POLICY IF EXISTS refresh_tokens_owner_only ON public.refresh_tokens;
CREATE POLICY refresh_tokens_owner_only
  ON public.refresh_tokens
  FOR ALL
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS user_accounts_owner_only ON public.user_accounts;
CREATE POLICY user_accounts_owner_only
  ON public.user_accounts
  FOR ALL
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- 2) Security Definer Views fixes
-- ---------------------------------------------------------------------------

ALTER VIEW IF EXISTS public.portes_activos SET (security_invoker = on);
ALTER VIEW IF EXISTS public.vw_esg_emissions_summary SET (security_invoker = on);

-- ---------------------------------------------------------------------------
-- 3) Mutable Search Path fixes
-- ---------------------------------------------------------------------------

ALTER FUNCTION public.app_assigned_vehiculo_id() SET search_path = public;
ALTER FUNCTION public.app_current_cliente_id() SET search_path = public;
ALTER FUNCTION public.app_current_empresa_id() SET search_path = public;
ALTER FUNCTION public.app_current_user_role() SET search_path = public;
ALTER FUNCTION public.app_rbac_role() SET search_path = public;
ALTER FUNCTION public.check_empresa_id_lock() SET search_path = public;
ALTER FUNCTION public.check_fiscal_immutability() SET search_path = public;
ALTER FUNCTION public.check_limite_starter() SET search_path = public;
