-- Chat persistence (tenant-scoped): sessions + messages
-- Endpoint canónico: POST /api/v1/advisor/ask

CREATE TABLE IF NOT EXISTS public.chat_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  created_by_profile_id uuid,
  title text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  archived_at timestamptz,
  archived_reason text,
  deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS public.chat_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES public.chat_sessions (id) ON DELETE CASCADE,
  empresa_id uuid NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  created_by_profile_id uuid,
  role text NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content text NOT NULL CHECK (length(trim(content)) > 0),
  model text,
  tokens integer,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_empresa_updated
  ON public.chat_sessions (empresa_id, updated_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_chat_sessions_empresa_archived
  ON public.chat_sessions (empresa_id, archived_at, updated_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
  ON public.chat_messages (session_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_chat_messages_empresa_created
  ON public.chat_messages (empresa_id, created_at DESC);

CREATE OR REPLACE FUNCTION public._chat_sessions_touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_chat_sessions_touch_updated_at ON public.chat_sessions;
CREATE TRIGGER trg_chat_sessions_touch_updated_at
  BEFORE UPDATE ON public.chat_sessions
  FOR EACH ROW
  EXECUTE PROCEDURE public._chat_sessions_touch_updated_at();

ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS chat_sessions_select ON public.chat_sessions;
CREATE POLICY chat_sessions_select ON public.chat_sessions
  FOR SELECT TO authenticated
  USING (
    deleted_at IS NULL
    AND public.app_current_empresa_id() IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager', 'gestor', 'admin')
  );

DROP POLICY IF EXISTS chat_sessions_insert ON public.chat_sessions;
CREATE POLICY chat_sessions_insert ON public.chat_sessions
  FOR INSERT TO authenticated
  WITH CHECK (
    public.app_current_empresa_id() IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager', 'admin')
  );

DROP POLICY IF EXISTS chat_sessions_update ON public.chat_sessions;
CREATE POLICY chat_sessions_update ON public.chat_sessions
  FOR UPDATE TO authenticated
  USING (
    deleted_at IS NULL
    AND public.app_current_empresa_id() IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager', 'admin')
  )
  WITH CHECK (
    public.app_current_empresa_id() IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager', 'admin')
  );

DROP POLICY IF EXISTS chat_messages_select ON public.chat_messages;
CREATE POLICY chat_messages_select ON public.chat_messages
  FOR SELECT TO authenticated
  USING (
    public.app_current_empresa_id() IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager', 'gestor', 'admin')
    AND EXISTS (
      SELECT 1
      FROM public.chat_sessions s
      WHERE s.id = chat_messages.session_id
        AND s.deleted_at IS NULL
        AND s.empresa_id::text = public.app_current_empresa_id()::text
    )
  );

DROP POLICY IF EXISTS chat_messages_insert ON public.chat_messages;
CREATE POLICY chat_messages_insert ON public.chat_messages
  FOR INSERT TO authenticated
  WITH CHECK (
    public.app_current_empresa_id() IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager', 'admin')
    AND EXISTS (
      SELECT 1
      FROM public.chat_sessions s
      WHERE s.id = chat_messages.session_id
        AND s.deleted_at IS NULL
        AND s.empresa_id::text = public.app_current_empresa_id()::text
    )
  );

GRANT SELECT, INSERT, UPDATE ON public.chat_sessions TO authenticated;
GRANT SELECT, INSERT ON public.chat_messages TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.chat_sessions TO service_role;
GRANT SELECT, INSERT ON public.chat_messages TO service_role;

CREATE OR REPLACE FUNCTION public.archive_inactive_chat_sessions(
  p_empresa_id uuid,
  p_inactive_days integer DEFAULT 30
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_count integer := 0;
BEGIN
  UPDATE public.chat_sessions
  SET archived_at = now(),
      archived_reason = 'inactive',
      updated_at = now()
  WHERE empresa_id = p_empresa_id
    AND deleted_at IS NULL
    AND archived_at IS NULL
    AND updated_at < (now() - make_interval(days => GREATEST(7, p_inactive_days)));

  GET DIAGNOSTICS v_count = ROW_COUNT;
  RETURN v_count;
END;
$$;

CREATE OR REPLACE FUNCTION public.soft_delete_expired_chat_sessions(
  p_empresa_id uuid,
  p_retention_days integer DEFAULT 180
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_count integer := 0;
BEGIN
  UPDATE public.chat_sessions
  SET deleted_at = now(),
      updated_at = now()
  WHERE empresa_id = p_empresa_id
    AND deleted_at IS NULL
    AND created_at < (now() - make_interval(days => GREATEST(30, p_retention_days)));

  GET DIAGNOSTICS v_count = ROW_COUNT;
  RETURN v_count;
END;
$$;

GRANT EXECUTE ON FUNCTION public.archive_inactive_chat_sessions(uuid, integer) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.soft_delete_expired_chat_sessions(uuid, integer) TO authenticated, service_role;
