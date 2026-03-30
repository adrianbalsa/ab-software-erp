-- >>> 13_20260326_add_gocardless_to_profiles.sql.json
-- Persistencia GoCardless para pagos automatizados (mandato SEPA / customer linking).
-- Campos críticos para el flujo de cobro automático del portal cliente.

-- 1) Profiles: referencia estable al customer remoto de GoCardless.
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS gocardless_customer_id text;

COMMENT ON COLUMN public.profiles.gocardless_customer_id IS
  'ID de customer en GoCardless (critical payment identity for automated collections).';

-- Índice único para búsquedas rápidas y evitar colisiones de customer remoto.
CREATE UNIQUE INDEX IF NOT EXISTS ux_profiles_gocardless_customer_id
  ON public.profiles (gocardless_customer_id)
  WHERE gocardless_customer_id IS NOT NULL;

-- 2) Clientes: estado de mandato activo para UX/flujo de cobro.
ALTER TABLE public.clientes
  ADD COLUMN IF NOT EXISTS mandato_activo boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.clientes.mandato_activo IS
  'TRUE cuando existe mandato SEPA activo para cobro automático vía GoCardless.';

-- 3) set_rbac_session: no requiere cambios funcionales para estos campos.
-- Ambos campos se leen/escriben dentro de filas ya protegidas por las políticas RLS
-- vigentes de profiles/clientes en base a app_current_empresa_id() y app_current_cliente_id().
COMMENT ON FUNCTION public.set_rbac_session(text, uuid, uuid, uuid) IS
  'Fija app.rbac_role, app.assigned_vehiculo_id, app.current_profile_id y app.cliente_id (portal). Compatible con campos GoCardless de profiles/clientes.';



-- >>> 14_20260326_flota_vencimientos_alertas.sql.json
-- Vencimientos ITV / seguro para alertas de flota [cite: 2026-03-22]
-- km_proximo_servicio ya existe en esquema legacy (supabase_schema.sql).

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS itv_vencimiento date;

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS seguro_vencimiento date;

COMMENT ON COLUMN public.flota.itv_vencimiento IS 'Próxima ITV (fecha límite)';
COMMENT ON COLUMN public.flota.seguro_vencimiento IS 'Vencimiento póliza seguro';


-- >>> 15_20260326_master_soft_delete_clientes_empresas.sql.json
-- D2/D3: columnas de borrado lógico en maestras (idempotente).
-- Ejecutar en Supabase si las tablas aún no tienen `deleted_at`.

ALTER TABLE public.clientes
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

COMMENT ON COLUMN public.clientes.deleted_at IS 'NULL = activo; IS NOT NULL = archivado (UI oculta)';
COMMENT ON COLUMN public.empresas.deleted_at IS 'NULL = activo; IS NOT NULL = empresa archivada (admin)';


-- >>> 16_20260327_portes_co2_emitido_esg.sql.json
-- Huella CO2 por porte (motor ESG Enterprise): kg CO2 estimados (distancia × toneladas × factor).
ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS co2_emitido numeric;

ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS peso_ton numeric;

COMMENT ON COLUMN public.portes.co2_emitido IS
  'kg CO2 estimados (Enterprise): distancia_km × peso_ton × factor_emision; ver eco_service.calcular_huella_porte';

COMMENT ON COLUMN public.portes.peso_ton IS
  'Toneladas de carga (opcional API); si NULL, se estima desde bultos al calcular huella.';


-- >>> 17_20260328_empresas_stripe_billing.sql.json
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


-- >>> 18_20260330_facturas_xml_verifactu.sql.json
-- XML de alta VeriFactu (registro exportable / trazabilidad) persistido con la factura.
ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS xml_verifactu TEXT;

COMMENT ON COLUMN public.facturas.xml_verifactu IS
  'XML UTF-8 de registro VeriFactu (Cabecera, RegistroFactura, Desglose) generado al sellar el hash';


-- >>> 19_20260401_esg_flota_porte_vehiculo.sql.json
-- ESG: factor de emisión por vehículo (kg CO₂ / (t·km)) y asignación opcional de porte → flota.
ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS factor_emision_co2_tkm NUMERIC(14, 8);

COMMENT ON COLUMN public.flota.factor_emision_co2_tkm IS
  'Opcional: factor kg CO₂eq por tonelada·km; si NULL se deriva de tipo_motor en la API.';

ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS vehiculo_id UUID REFERENCES public.flota (id);

CREATE INDEX IF NOT EXISTS idx_portes_vehiculo_id
  ON public.portes (vehiculo_id)
  WHERE vehiculo_id IS NOT NULL;

COMMENT ON COLUMN public.portes.vehiculo_id IS
  'Vehículo asignado al porte (ESG); NULL = factor global empresa.';


-- >>> 20_20260403_infra_health_logs.sql.json
-- Logs proactivos de salud (latencia DB, peticiones lentas). Sin credenciales en `message`.
CREATE TABLE IF NOT EXISTS public.infra_health_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  source text NOT NULL,
  status text NOT NULL,
  latency_ms double precision,
  message text,
  path text,
  method text
);

CREATE INDEX IF NOT EXISTS infra_health_logs_created_at_idx
  ON public.infra_health_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS infra_health_logs_source_idx
  ON public.infra_health_logs (source);

COMMENT ON TABLE public.infra_health_logs IS
  'SRE: salud DB y latencia API; los mensajes deben estar sanitizados (sin URI con contraseña).';


-- >>> 21_20260404_portes_activos_math_engine_view.sql.json
-- Vista operativa para mapa de flota:
-- - Portes activos (pendientes) con asignación de vehículo.
-- - Margen estimado por porte basado en la métrica del Math Engine (margen EBITDA/km histórico).
-- - Coordenadas y matrícula para consumo directo por API `/flota/estado-actual`.

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS lat double precision,
  ADD COLUMN IF NOT EXISTS lng double precision;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vehiculos'
  ) THEN
    EXECUTE '
      ALTER TABLE public.vehiculos
        ADD COLUMN IF NOT EXISTS lat double precision,
        ADD COLUMN IF NOT EXISTS lng double precision
    ';
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_portes_activos_lookup
  ON public.portes (empresa_id, estado, vehiculo_id)
  WHERE deleted_at IS NULL;

DO $$
DECLARE
  vehiculos_exists boolean;
  sql_text text;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vehiculos'
  ) INTO vehiculos_exists;

  sql_text := '
    CREATE OR REPLACE VIEW public.portes_activos AS
    WITH ingresos AS (
      SELECT
        f.empresa_id,
        SUM(
          CASE
            WHEN f.base_imponible IS NOT NULL THEN COALESCE(f.base_imponible, 0)::double precision
            ELSE GREATEST(COALESCE(f.total_factura, 0)::double precision - COALESCE(f.cuota_iva, 0)::double precision, 0)
          END
        ) AS ingresos_netos_sin_iva,
        SUM(COALESCE(f.total_km_estimados_snapshot, 0)::double precision) AS km_facturados
      FROM public.facturas f
      GROUP BY f.empresa_id
    ),
    gastos AS (
      SELECT
        g.empresa_id,
        SUM(
          GREATEST(
            COALESCE(g.total_eur, g.total_chf, 0)::double precision
            - CASE
                WHEN COALESCE(g.iva, 0)::double precision > 0 THEN COALESCE(g.iva, 0)::double precision
                ELSE 0
              END,
            0
          )
        ) AS gastos_netos_sin_iva
      FROM public.gastos g
      WHERE g.deleted_at IS NULL
      GROUP BY g.empresa_id
    ),
    margen_empresa AS (
      SELECT
        i.empresa_id,
        CASE
          WHEN COALESCE(i.km_facturados, 0) > 0
            THEN (COALESCE(i.ingresos_netos_sin_iva, 0) - COALESCE(ga.gastos_netos_sin_iva, 0)) / i.km_facturados
          ELSE 0
        END AS margen_km_eur
      FROM ingresos i
      LEFT JOIN gastos ga ON ga.empresa_id = i.empresa_id
    )
    SELECT
      p.id,
      p.empresa_id,
      p.vehiculo_id,
      p.origen,
      p.destino,';

  IF vehiculos_exists THEN
    sql_text := sql_text || '
      COALESCE(vv.matricula, vf.matricula) AS matricula,
      COALESCE(vv.lat, vf.lat) AS lat,
      COALESCE(vv.lng, vf.lng) AS lng,';
  ELSE
    sql_text := sql_text || '
      vf.matricula AS matricula,
      vf.lat AS lat,
      vf.lng AS lng,';
  END IF;

  sql_text := sql_text || '
      COALESCE(me.margen_km_eur, 0)::double precision AS margen_km_eur,
      ROUND(
        (COALESCE(p.km_estimados, 0)::double precision * COALESCE(me.margen_km_eur, 0)::double precision)::numeric,
        2
      )::double precision AS margen_estimado
    FROM public.portes p
    LEFT JOIN public.flota vf
      ON vf.id = p.vehiculo_id
     AND vf.empresa_id = p.empresa_id
     AND vf.deleted_at IS NULL';

  IF vehiculos_exists THEN
    sql_text := sql_text || '
    LEFT JOIN public.vehiculos vv
      ON vv.id = p.vehiculo_id
     AND vv.empresa_id = p.empresa_id
     AND vv.deleted_at IS NULL';
  END IF;

  sql_text := sql_text || '
    LEFT JOIN margen_empresa me
      ON me.empresa_id = p.empresa_id
    WHERE p.estado = ''pendiente''
      AND p.deleted_at IS NULL
      AND p.vehiculo_id IS NOT NULL
  ';

  EXECUTE sql_text;
END $$;

COMMENT ON VIEW public.portes_activos IS
  'Portes pendientes con vehículo asignado, coordenadas operativas y margen_estimado (Math Engine: margen EBITDA/km × km del porte).';

COMMENT ON COLUMN public.portes_activos.margen_km_eur IS
  'Margen operativo medio EUR/km por empresa (ingresos netos sin IVA - gastos netos sin IVA) / km facturados.';

COMMENT ON COLUMN public.portes_activos.margen_estimado IS
  'Margen estimado por porte = km_estimados del porte × margen_km_eur de la empresa.';


-- >>> 22_20260405_rbac_user_role_profiles_portes_rls.sql.json
-- =============================================================================
-- RBAC empresarial: tipo user_role, perfiles operativos, sesión app.rbac_role
-- y políticas RLS en public.portes (owner/traffic_manager vs driver).
-- Requisitos: public.set_empresa_context (20260324) y conexión PostgREST con
-- el JWT del usuario para que el backend invoque set_empresa_context + set_rbac_session.
-- =============================================================================

DO $$ BEGIN
  CREATE TYPE public.user_role AS ENUM ('owner', 'traffic_manager', 'driver');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'profiles'
  ) THEN
    ALTER TABLE public.profiles
      ADD COLUMN IF NOT EXISTS role public.user_role NOT NULL DEFAULT 'owner'::public.user_role;
    ALTER TABLE public.profiles
      ADD COLUMN IF NOT EXISTS assigned_vehiculo_id UUID REFERENCES public.flota (id) ON DELETE SET NULL;

    COMMENT ON COLUMN public.profiles.role IS
      'Rol RBAC operativo: owner (total), traffic_manager (operativo sin facturación global), driver (solo lectura portes asignados).';
    COMMENT ON COLUMN public.profiles.assigned_vehiculo_id IS
      'Vehículo (flota) asignado al chófer; obligatorio para aislar filas portes vía RLS si role=driver.';

    -- Histórico: conservar privilegios (equivalente a owner operativo hasta reasignación).
    -- Nuevos registros pueden fijar role en la app; DEFAULT owner mantiene compatibilidad Zero-Downtime.
  END IF;
END $$;

-- Variables de sesión (misma transacción que set_empresa_context en la petición API).
CREATE OR REPLACE FUNCTION public.set_rbac_session(
  p_rbac_role text,
  p_assigned_vehiculo_id uuid DEFAULT NULL
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
END;
$$;

COMMENT ON FUNCTION public.set_rbac_session(text, uuid) IS
  'Fija app.rbac_role y app.assigned_vehiculo_id para políticas RLS (invocar tras set_empresa_context).';

CREATE OR REPLACE FUNCTION public.app_rbac_role()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT COALESCE(
    NULLIF(trim(both from current_setting('app.rbac_role', true)), ''),
    'owner'
  );
$$;

CREATE OR REPLACE FUNCTION public.app_assigned_vehiculo_id()
RETURNS uuid
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  s text;
BEGIN
  s := NULLIF(trim(both from current_setting('app.assigned_vehiculo_id', true)), '');
  IF s IS NULL OR s = '' THEN
    RETURN NULL;
  END IF;
  RETURN s::uuid;
EXCEPTION
  WHEN invalid_text_representation THEN
    RETURN NULL;
END;
$$;

-- ─── PORTES: políticas RBAC ────────────────────────────────────────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'portes'
  ) THEN
    ALTER TABLE public.portes ENABLE ROW LEVEL SECURITY;

    DROP POLICY IF EXISTS portes_select_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_insert_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_update_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_delete_tenant ON public.portes;
    DROP POLICY IF EXISTS portes_select_rbac ON public.portes;
    DROP POLICY IF EXISTS portes_insert_rbac ON public.portes;
    DROP POLICY IF EXISTS portes_update_rbac ON public.portes;
    DROP POLICY IF EXISTS portes_delete_rbac ON public.portes;

    CREATE POLICY portes_select_rbac ON public.portes
      FOR SELECT
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND (
          public.app_rbac_role() IN ('owner', 'traffic_manager')
          OR (
            public.app_rbac_role() = 'driver'
            AND vehiculo_id IS NOT NULL
            AND vehiculo_id = public.app_assigned_vehiculo_id()
            AND public.app_assigned_vehiculo_id() IS NOT NULL
          )
        )
      );

    CREATE POLICY portes_insert_rbac ON public.portes
      FOR INSERT
      WITH CHECK (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );

    CREATE POLICY portes_update_rbac ON public.portes
      FOR UPDATE
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      )
      WITH CHECK (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );

    CREATE POLICY portes_delete_rbac ON public.portes
      FOR DELETE
      USING (
        empresa_id::text = public.app_current_empresa_id()::text
        AND public.app_rbac_role() IN ('owner', 'traffic_manager')
      );
  END IF;
END $$;


-- >>> 23_20260424_audit_logs_triggers.sql.json
-- =============================================================================
-- Audit logs pasivos (triggers) — portes, facturas, gastos
-- Captura INSERT/UPDATE/DELETE sin tocar la API FastAPI.
-- auth.uid() rellena changed_by cuando la mutación llega con JWT de usuario;
-- con service_role suele ser NULL (acción de sistema / backend).
-- =============================================================================

CREATE TYPE public.audit_action AS ENUM ('INSERT', 'UPDATE', 'DELETE');

CREATE TABLE IF NOT EXISTS public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL,
  table_name varchar(128) NOT NULL,
  record_id text NOT NULL,
  action public.audit_action NOT NULL,
  old_data jsonb,
  new_data jsonb,
  changed_by uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_empresa_created
  ON public.audit_logs (empresa_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_logs_table_record
  ON public.audit_logs (table_name, record_id);

COMMENT ON TABLE public.audit_logs IS
  'Trazabilidad de cambios en tablas críticas (triggers). record_id en texto para cualquier tipo de PK.';
COMMENT ON COLUMN public.audit_logs.record_id IS
  'Valor textual de la PK de la fila afectada (UUID u otro).';
COMMENT ON COLUMN public.audit_logs.changed_by IS
  'auth.users.id cuando existe contexto JWT; NULL en escrituras con service_role u operaciones de sistema.';

-- ─── Función genérica de auditoría ───────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.audit_row_change()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_empresa uuid;
  v_old jsonb;
  v_new jsonb;
  v_record_id text;
  v_action public.audit_action;
BEGIN
  IF TG_OP = 'INSERT' THEN
    v_action := 'INSERT';
    v_old := NULL;
    v_new := to_jsonb(NEW);
    v_empresa := NEW.empresa_id;
  ELSIF TG_OP = 'UPDATE' THEN
    v_action := 'UPDATE';
    v_old := to_jsonb(OLD);
    v_new := to_jsonb(NEW);
    v_empresa := NEW.empresa_id;
  ELSIF TG_OP = 'DELETE' THEN
    v_action := 'DELETE';
    v_old := to_jsonb(OLD);
    v_new := NULL;
    v_empresa := OLD.empresa_id;
  ELSE
    RETURN COALESCE(NEW, OLD);
  END IF;

  v_record_id := coalesce(v_new->>'id', v_old->>'id');
  IF v_record_id IS NULL OR length(trim(v_record_id)) = 0 THEN
    v_record_id := gen_random_uuid()::text;
  END IF;

  INSERT INTO public.audit_logs (
    empresa_id,
    table_name,
    record_id,
    action,
    old_data,
    new_data,
    changed_by
  ) VALUES (
    v_empresa,
    TG_TABLE_NAME::varchar(128),
    v_record_id,
    v_action,
    v_old,
    v_new,
    auth.uid()
  );

  RETURN COALESCE(NEW, OLD);
END;
$$;

COMMENT ON FUNCTION public.audit_row_change() IS
  'Trigger genérico AFTER INSERT/UPDATE/DELETE → public.audit_logs.';

-- ─── Triggers en tablas críticas ─────────────────────────────────────────────

DROP TRIGGER IF EXISTS trg_audit_row_portes ON public.portes;
CREATE TRIGGER trg_audit_row_portes
  AFTER INSERT OR UPDATE OR DELETE ON public.portes
  FOR EACH ROW
  EXECUTE PROCEDURE public.audit_row_change();

DROP TRIGGER IF EXISTS trg_audit_row_facturas ON public.facturas;
CREATE TRIGGER trg_audit_row_facturas
  AFTER INSERT OR UPDATE OR DELETE ON public.facturas
  FOR EACH ROW
  EXECUTE PROCEDURE public.audit_row_change();

DROP TRIGGER IF EXISTS trg_audit_row_gastos ON public.gastos;
CREATE TRIGGER trg_audit_row_gastos
  AFTER INSERT OR UPDATE OR DELETE ON public.gastos
  FOR EACH ROW
  EXECUTE PROCEDURE public.audit_row_change();

-- ─── RLS: lectura por tenant (misma sesión que set_empresa_context) ─────────

ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS audit_logs_select_tenant ON public.audit_logs;
CREATE POLICY audit_logs_select_tenant ON public.audit_logs
  FOR SELECT
  USING (
    public.app_current_empresa_id()::text IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
  );

-- Sin política INSERT/UPDATE/DELETE para roles autenticados: solo el trigger (SECURITY DEFINER) escribe.

GRANT SELECT ON public.audit_logs TO authenticated;
GRANT SELECT ON public.audit_logs TO service_role;


-- >>> 24_20260426_verifactu_fingerprint_finalizacion.sql.json
-- =============================================================================
-- VeriFactu: huella encadenada (fingerprint), QR de cotejo, finalización atómica
-- =============================================================================

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS fingerprint text,
  ADD COLUMN IF NOT EXISTS prev_fingerprint text,
  ADD COLUMN IF NOT EXISTS qr_code_url text,
  ADD COLUMN IF NOT EXISTS is_finalized boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.facturas.fingerprint IS
  'SHA-256 hex encadenado (NIF, número, fecha, total + huella anterior o semilla genesis).';
COMMENT ON COLUMN public.facturas.prev_fingerprint IS
  'Huella fingerprint de la factura finalizada inmediatamente anterior (NULL en la primera).';
COMMENT ON COLUMN public.facturas.qr_code_url IS
  'URL de verificación AEAT (TIKE) codificada en el QR.';
COMMENT ON COLUMN public.facturas.is_finalized IS
  'TRUE tras la operación de finalización; bloquea borrado y mutaciones posteriores.';

-- Integridad: misma empresa no puede repetir huella
CREATE UNIQUE INDEX IF NOT EXISTS uq_facturas_empresa_fingerprint
  ON public.facturas (empresa_id, fingerprint)
  WHERE fingerprint IS NOT NULL AND length(trim(fingerprint)) > 0;

-- Datos ya sellados con hash_registro: tratarlos como finalizados para no exigir re-finalizar
UPDATE public.facturas
SET is_finalized = true,
    fingerprint = coalesce(nullif(trim(fingerprint), ''), nullif(trim(hash_registro), ''))
WHERE hash_registro IS NOT NULL
  AND length(trim(hash_registro::text)) > 0
  AND (is_finalized IS NOT TRUE OR fingerprint IS NULL);

-- ─── Inmutabilidad facturas: permite UNA actualización de finalización ─────

CREATE OR REPLACE FUNCTION public.enforce_immutable_facturas()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF current_setting('role', true) = 'service_role' THEN
    IF TG_OP = 'DELETE' THEN
      RETURN OLD;
    END IF;
    RETURN NEW;
  END IF;

  IF TG_OP = 'UPDATE' THEN
    -- Transición explícita a finalizada con huella extendida (sin mutar hash_registro fiscal)
    IF OLD.hash_registro IS NOT NULL
       AND length(trim(OLD.hash_registro::text)) > 0
       AND COALESCE(OLD.is_finalized, false) IS FALSE
       AND COALESCE(NEW.is_finalized, false) IS TRUE
       AND NEW.fingerprint IS NOT NULL
       AND length(trim(NEW.fingerprint::text)) > 0
    THEN
      RETURN NEW;
    END IF;

    IF OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0 THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW: UPDATE prohibido una vez fijado hash_registro (tabla facturas)';
    END IF;
    RETURN NEW;

  ELSIF TG_OP = 'DELETE' THEN
    IF COALESCE(OLD.is_finalized, false) IS TRUE THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW: DELETE prohibido para factura finalizada VeriFactu (tabla facturas)';
    END IF;
    IF OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0 THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW: DELETE prohibido una vez fijado hash_registro (tabla facturas)';
    END IF;
    RETURN OLD;
  END IF;

  RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS trg_facturas_immutable_hash ON public.facturas;
CREATE TRIGGER trg_facturas_immutable_hash
  BEFORE UPDATE OR DELETE ON public.facturas
  FOR EACH ROW
  EXECUTE PROCEDURE public.enforce_immutable_facturas();


-- >>> 25_20260427_aeat_verifactu_envios.sql.json
-- AEAT SIF / VeriFactu: registro de envíos y metadatos en facturas finalizadas.
-- Permite actualizar solo columnas aeat_sif_* en facturas ya finalizadas (trigger).

CREATE TABLE IF NOT EXISTS public.verifactu_envios (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES public.empresas (id) ON DELETE CASCADE,
  factura_id bigint NOT NULL REFERENCES public.facturas (id) ON DELETE RESTRICT,
  estado text NOT NULL,
  codigo_error text,
  descripcion_error text,
  csv_aeat text,
  http_status int,
  response_snippet text,
  soap_action text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_verifactu_envios_factura_id
  ON public.verifactu_envios (factura_id);

CREATE INDEX IF NOT EXISTS idx_verifactu_envios_empresa_id
  ON public.verifactu_envios (empresa_id);

COMMENT ON TABLE public.verifactu_envios IS
  'Intentos de remisión SIF VeriFactu a la AEAT (por factura).';
COMMENT ON COLUMN public.verifactu_envios.csv_aeat IS
  'Identificador o trazas CSV devueltas por la AEAT cuando aplica.';

ALTER TABLE public.empresas
  ADD COLUMN IF NOT EXISTS aeat_client_cert_path text,
  ADD COLUMN IF NOT EXISTS aeat_client_key_path text,
  ADD COLUMN IF NOT EXISTS aeat_client_p12_path text;

COMMENT ON COLUMN public.empresas.aeat_client_cert_path IS
  'Ruta PEM certificado cliente TLS (mutua); alternativa a variables globales AEAT_CLIENT_* .';
COMMENT ON COLUMN public.empresas.aeat_client_key_path IS
  'Ruta PEM clave privada TLS.';
COMMENT ON COLUMN public.empresas.aeat_client_p12_path IS
  'Ruta bundle PKCS#12 (.p12); contraseña vía AEAT_CLIENT_P12_PASSWORD en el servidor.';

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS aeat_sif_estado text,
  ADD COLUMN IF NOT EXISTS aeat_sif_csv text,
  ADD COLUMN IF NOT EXISTS aeat_sif_codigo text,
  ADD COLUMN IF NOT EXISTS aeat_sif_descripcion text,
  ADD COLUMN IF NOT EXISTS aeat_sif_actualizado_en timestamptz;

COMMENT ON COLUMN public.facturas.aeat_sif_estado IS
  'Estado remisión SIF: aceptado, aceptado_con_errores, rechazado, error_tecnico, pendiente, omitido.';

-- ─── Trigger inmutabilidad: permitir actualizar solo columnas AEAT ─────────

CREATE OR REPLACE FUNCTION public.enforce_immutable_facturas()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  new_j jsonb;
  old_j jsonb;
BEGIN
  IF current_setting('role', true) = 'service_role' THEN
    IF TG_OP = 'DELETE' THEN
      RETURN OLD;
    END IF;
    RETURN NEW;
  END IF;

  IF TG_OP = 'UPDATE' THEN
    IF OLD.hash_registro IS NOT NULL
       AND length(trim(OLD.hash_registro::text)) > 0
       AND COALESCE(OLD.is_finalized, false) IS FALSE
       AND COALESCE(NEW.is_finalized, false) IS TRUE
       AND NEW.fingerprint IS NOT NULL
       AND length(trim(NEW.fingerprint::text)) > 0
    THEN
      RETURN NEW;
    END IF;

    IF OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0 THEN
      IF COALESCE(OLD.is_finalized, false) IS TRUE
         AND COALESCE(NEW.is_finalized, false) IS TRUE
      THEN
        new_j := row_to_json(NEW)::jsonb;
        old_j := row_to_json(OLD)::jsonb;
        new_j := new_j
          - 'aeat_sif_estado' - 'aeat_sif_csv' - 'aeat_sif_codigo'
          - 'aeat_sif_descripcion' - 'aeat_sif_actualizado_en';
        old_j := old_j
          - 'aeat_sif_estado' - 'aeat_sif_csv' - 'aeat_sif_codigo'
          - 'aeat_sif_descripcion' - 'aeat_sif_actualizado_en';
        IF new_j IS NOT DISTINCT FROM old_j THEN
          RETURN NEW;
        END IF;
      END IF;
      RAISE EXCEPTION
        'IMMUTABLE_ROW: UPDATE prohibido una vez fijado hash_registro (tabla facturas)';
    END IF;
    RETURN NEW;

  ELSIF TG_OP = 'DELETE' THEN
    IF COALESCE(OLD.is_finalized, false) IS TRUE THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW: DELETE prohibido para factura finalizada VeriFactu (tabla facturas)';
    END IF;
    IF OLD.hash_registro IS NOT NULL AND length(trim(OLD.hash_registro::text)) > 0 THEN
      RAISE EXCEPTION
        'IMMUTABLE_ROW: DELETE prohibido una vez fijado hash_registro (tabla facturas)';
    END IF;
    RETURN OLD;
  END IF;

  RETURN COALESCE(NEW, OLD);
END;
$$;

-- Fix typo if any: I introduced _IF_label by mistake - need to remove