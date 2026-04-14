-- POD: firma consignatario, nombre, fecha entrega real, conductor explícito opcional.
-- RLS: permite UPDATE a conductores (vehículo asignado o conductor_asignado_id).

ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS firma_consignatario_b64 text,
  ADD COLUMN IF NOT EXISTS firma_consignatario_url text,
  ADD COLUMN IF NOT EXISTS nombre_consignatario_final text,
  ADD COLUMN IF NOT EXISTS fecha_entrega_real timestamptz,
  ADD COLUMN IF NOT EXISTS conductor_asignado_id uuid REFERENCES public.profiles (id) ON DELETE SET NULL;

COMMENT ON COLUMN public.portes.firma_consignatario_b64 IS 'Firma PNG/SVG en Base64 (data URL o raw).';
COMMENT ON COLUMN public.portes.firma_consignatario_url IS 'URL en Storage/CDN si la firma no se guarda en fila.';
COMMENT ON COLUMN public.portes.nombre_consignatario_final IS 'Nombre quien firma la entrega.';
COMMENT ON COLUMN public.portes.fecha_entrega_real IS 'Marca hora de la entrega confirmada.';
COMMENT ON COLUMN public.portes.conductor_asignado_id IS 'Opcional: perfil (profiles.id) asignado al porte si no basta vehículo.';

-- Estado: añadir Entregado (ciclo operativo previo a facturación).
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'portes_estado_check' AND conrelid = 'public.portes'::regclass
  ) THEN
    ALTER TABLE public.portes DROP CONSTRAINT portes_estado_check;
  END IF;
END $$;

ALTER TABLE public.portes
  ADD CONSTRAINT portes_estado_check
  CHECK (estado IN ('pendiente', 'Entregado', 'facturado'));

-- Sesión: perfil actual (para RLS conductor explícito).
CREATE OR REPLACE FUNCTION public.set_rbac_session(
  p_rbac_role text,
  p_assigned_vehiculo_id uuid DEFAULT NULL,
  p_profile_id uuid DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  r text;
BEGIN
  r := lower(trim(both from coalesce(p_rbac_role, 'owner')));
  IF r NOT IN ('owner', 'traffic_manager', 'driver') THEN
    r := 'owner';
  END IF;
  PERFORM set_config('app.rbac_role', r, true);
  IF p_assigned_vehiculo_id IS NULL THEN
    PERFORM set_config('app.assigned_vehiculo_id', '', true);
  ELSE
    PERFORM set_config('app.assigned_vehiculo_id', p_assigned_vehiculo_id::text, true);
  END IF;
  IF p_profile_id IS NULL THEN
    PERFORM set_config('app.current_profile_id', '', true);
  ELSE
    PERFORM set_config('app.current_profile_id', p_profile_id::text, true);
  END IF;
END;
$$;

COMMENT ON FUNCTION public.set_rbac_session(text, uuid, uuid) IS
  'Fija app.rbac_role, app.assigned_vehiculo_id y app.current_profile_id (perfil JWT).';

CREATE OR REPLACE FUNCTION public.app_current_profile_id()
RETURNS uuid
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  s text;
BEGIN
  s := NULLIF(trim(both from current_setting('app.current_profile_id', true)), '');
  IF s IS NULL OR s = '' THEN
    RETURN NULL;
  END IF;
  RETURN s::uuid;
EXCEPTION
  WHEN invalid_text_representation THEN
    RETURN NULL;
END;
$$;

-- Política UPDATE para conductores (firma entrega).
DROP POLICY IF EXISTS portes_update_driver_entrega ON public.portes;
CREATE POLICY portes_update_driver_entrega ON public.portes
  FOR UPDATE
  USING (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'driver'
    AND (
      (
        vehiculo_id IS NOT NULL
        AND public.app_assigned_vehiculo_id() IS NOT NULL
        AND vehiculo_id = public.app_assigned_vehiculo_id()
      )
      OR (
        conductor_asignado_id IS NOT NULL
        AND conductor_asignado_id = public.app_current_profile_id()
        AND public.app_current_profile_id() IS NOT NULL
      )
    )
  )
  WITH CHECK (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() = 'driver'
    AND (
      (
        vehiculo_id IS NOT NULL
        AND public.app_assigned_vehiculo_id() IS NOT NULL
        AND vehiculo_id = public.app_assigned_vehiculo_id()
      )
      OR (
        conductor_asignado_id IS NOT NULL
        AND conductor_asignado_id = public.app_current_profile_id()
        AND public.app_current_profile_id() IS NOT NULL
      )
    )
  );
