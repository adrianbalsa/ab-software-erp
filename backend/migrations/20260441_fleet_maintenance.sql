-- Mantenimiento predictivo por km: odómetro y planes por vehículo (flota).
-- portes.vehiculo_id referencia public.flota(id); odometro_actual se actualiza al completar entrega.

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS odometro_actual integer NOT NULL DEFAULT 0;

COMMENT ON COLUMN public.flota.odometro_actual IS
  'Km acumulados operativos (suma de km de portes completados); independiente de km_actual legacy.';

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vehiculos'
  ) THEN
    EXECUTE '
      ALTER TABLE public.vehiculos
        ADD COLUMN IF NOT EXISTS odometro_actual integer NOT NULL DEFAULT 0
    ';
    EXECUTE '
      COMMENT ON COLUMN public.vehiculos.odometro_actual IS
        ''Odómetro operativo (sincronizado con flota cuando comparten id de vehículo).''
    ';
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.planes_mantenimiento (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  vehiculo_id uuid NOT NULL REFERENCES public.flota (id) ON DELETE CASCADE,
  tipo_tarea text NOT NULL,
  intervalo_km integer NOT NULL CHECK (intervalo_km > 0),
  ultimo_km_realizado integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_planes_mantenimiento_empresa_vehiculo
  ON public.planes_mantenimiento (empresa_id, vehiculo_id);

ALTER TABLE public.planes_mantenimiento ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS planes_mantenimiento_select_rbac ON public.planes_mantenimiento;
CREATE POLICY planes_mantenimiento_select_rbac ON public.planes_mantenimiento
  FOR SELECT
  USING (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager')
  );

DROP POLICY IF EXISTS planes_mantenimiento_insert_rbac ON public.planes_mantenimiento;
CREATE POLICY planes_mantenimiento_insert_rbac ON public.planes_mantenimiento
  FOR INSERT
  WITH CHECK (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager')
  );

DROP POLICY IF EXISTS planes_mantenimiento_update_rbac ON public.planes_mantenimiento;
CREATE POLICY planes_mantenimiento_update_rbac ON public.planes_mantenimiento
  FOR UPDATE
  USING (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager')
  )
  WITH CHECK (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager')
  );

DROP POLICY IF EXISTS planes_mantenimiento_delete_rbac ON public.planes_mantenimiento;
CREATE POLICY planes_mantenimiento_delete_rbac ON public.planes_mantenimiento
  FOR DELETE
  USING (
    empresa_id::text = public.app_current_empresa_id()::text
    AND public.app_rbac_role() IN ('owner', 'traffic_manager')
  );

COMMENT ON TABLE public.planes_mantenimiento IS
  'Planes de mantenimiento por intervalo de km; visión owner/traffic_manager (ADMIN/GESTOR).';

-- Incremento atómico de odómetro al completar porte (JWT + app_current_empresa_id).
CREATE OR REPLACE FUNCTION public.increment_vehiculo_odometro(
  p_empresa_id uuid,
  p_vehiculo_id uuid,
  p_km numeric
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_add integer;
BEGIN
  IF p_km IS NULL OR p_km <= 0 THEN
    RETURN;
  END IF;
  v_add := GREATEST(1, CEIL(p_km)::integer);
  IF p_empresa_id::text IS DISTINCT FROM public.app_current_empresa_id()::text THEN
    RAISE EXCEPTION 'increment_vehiculo_odometro: empresa no coincide con la sesión';
  END IF;

  UPDATE public.flota f
  SET odometro_actual = COALESCE(f.odometro_actual, 0) + v_add
  WHERE f.id = p_vehiculo_id
    AND f.empresa_id = p_empresa_id
    AND f.deleted_at IS NULL;

  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vehiculos'
  ) THEN
    UPDATE public.vehiculos v
    SET odometro_actual = COALESCE(v.odometro_actual, 0) + v_add
    WHERE v.id = p_vehiculo_id
      AND v.empresa_id = p_empresa_id
      AND (v.deleted_at IS NULL);
  END IF;
END;
$$;

COMMENT ON FUNCTION public.increment_vehiculo_odometro(uuid, uuid, numeric) IS
  'Suma km al odómetro en flota (y vehiculos si existe fila con mismo id). Requiere app_current_empresa_id.';

GRANT EXECUTE ON FUNCTION public.increment_vehiculo_odometro(uuid, uuid, numeric) TO authenticated;
GRANT EXECUTE ON FUNCTION public.increment_vehiculo_odometro(uuid, uuid, numeric) TO service_role;
