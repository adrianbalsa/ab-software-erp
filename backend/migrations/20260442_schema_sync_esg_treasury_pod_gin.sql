-- Sincronización final (auditoría): ESG combustible + tesorería/VeriFactu + POD + GIN analítico.
-- Idempotente: IF NOT EXISTS / CREATE OR REPLACE donde aplica.

-- ─── ESG: certificación motor (Euro V / VI / …) en flota y vehículos ─────────
ALTER TABLE public.vehiculos
  ADD COLUMN IF NOT EXISTS certificacion_emisiones text NOT NULL DEFAULT 'Euro VI';

ALTER TABLE public.flota
  ADD COLUMN IF NOT EXISTS certificacion_emisiones text NOT NULL DEFAULT 'Euro VI';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'vehiculos_certificacion_emisiones_check'
  ) THEN
    ALTER TABLE public.vehiculos
      ADD CONSTRAINT vehiculos_certificacion_emisiones_check
      CHECK (certificacion_emisiones IN ('Euro V', 'Euro VI', 'Electrico', 'Hibrido'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'flota_certificacion_emisiones_check'
  ) THEN
    ALTER TABLE public.flota
      ADD CONSTRAINT flota_certificacion_emisiones_check
      CHECK (certificacion_emisiones IN ('Euro V', 'Euro VI', 'Electrico', 'Hibrido'));
  END IF;
END $$;

ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS co2_emitido numeric;

COMMENT ON COLUMN public.portes.co2_emitido IS
  'kg CO2 estimados en el porte (motor ESG / distancia).';

-- Vista resumen (requiere co2_emitido en portes; COALESCE en SELECT).
CREATE OR REPLACE VIEW public.vw_esg_emissions_summary AS
SELECT
  p.id AS porte_id,
  p.empresa_id,
  p.cliente_id,
  p.vehiculo_id,
  (p.fecha::date) AS fecha,
  COALESCE(p.co2_emitido, 0)::numeric AS co2_kg,
  COALESCE(v.certificacion_emisiones, f.certificacion_emisiones, 'Euro VI'::text) AS certificacion_emisiones
FROM public.portes p
LEFT JOIN public.vehiculos v
  ON v.id = p.vehiculo_id
  AND v.empresa_id = p.empresa_id
  AND v.deleted_at IS NULL
LEFT JOIN public.flota f
  ON f.id = p.vehiculo_id
  AND f.empresa_id = p.empresa_id
  AND f.deleted_at IS NULL
WHERE p.deleted_at IS NULL;

COMMENT ON VIEW public.vw_esg_emissions_summary IS
  'Portes con co2_kg y certificación (COALESCE vehiculos, flota, Euro VI). Filtrar fecha en WHERE.';

-- ─── ESG auditoría combustible: CO2 automático (litros × factor × norma motor) ─
CREATE OR REPLACE FUNCTION public.esg_auditoria_calc_co2()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_empresa uuid := NEW.empresa_id;
  v_vid uuid := NEW.vehiculo_id;
  v_lit numeric := COALESCE(NEW.litros_consumidos, 0);
  v_cert text;
  v_base_kg_per_l numeric;
  v_norma numeric;
  v_tipo text;
BEGIN
  IF v_lit IS NULL OR v_lit <= 0 THEN
    NEW.co2_emitido_kg := 0;
    RETURN NEW;
  END IF;

  SELECT COALESCE(
    (SELECT certificacion_emisiones FROM public.vehiculos v
     WHERE v.id = v_vid AND v.empresa_id = v_empresa AND v.deleted_at IS NULL LIMIT 1),
    (SELECT certificacion_emisiones FROM public.flota f
     WHERE f.id = v_vid AND f.empresa_id = v_empresa AND f.deleted_at IS NULL LIMIT 1),
    'Euro VI'
  ) INTO v_cert;

  v_tipo := lower(trim(coalesce(NEW.tipo_combustible, '')));

  -- kg CO2 por litro (combustión aprox.); alineado con reporting transporte.
  v_base_kg_per_l := CASE
    WHEN v_tipo LIKE '%elect%' THEN 0
    WHEN v_tipo LIKE '%gasolina%' THEN 2.31
    WHEN v_tipo LIKE '%glp%' OR v_tipo LIKE '%gnc%' THEN 1.67
    ELSE 2.65
  END;

  v_norma := CASE trim(coalesce(v_cert, 'Euro VI'))
    WHEN 'Euro VI' THEN 1.0
    WHEN 'Euro V' THEN 1.15
    WHEN 'Electrico' THEN 0
    WHEN 'Hibrido' THEN 0.55
    ELSE 1.0
  END;

  NEW.co2_emitido_kg := round((v_lit * v_base_kg_per_l * v_norma)::numeric, 6);
  RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.esg_auditoria_calc_co2() IS
  'Calcula co2_emitido_kg en esg_auditoria: litros × factor combustible × certificación motor (Euro VI baseline).';

DROP TRIGGER IF EXISTS trg_esg_auditoria_calc_co2 ON public.esg_auditoria;
CREATE TRIGGER trg_esg_auditoria_calc_co2
  BEFORE INSERT OR UPDATE OF litros_consumidos, vehiculo_id, tipo_combustible
  ON public.esg_auditoria
  FOR EACH ROW
  EXECUTE FUNCTION public.esg_auditoria_calc_co2();

-- ─── Tesorería: vencimiento cobro + fecha estimada ligada a VeriFactu enviado_ok ─
ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS fecha_vencimiento date;

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS fecha_estimada_cobro date;

COMMENT ON COLUMN public.facturas.fecha_vencimiento IS
  'Vencimiento de cobro (AR); si NULL, la API puede usar fecha_emision + 30 días.';
COMMENT ON COLUMN public.facturas.fecha_estimada_cobro IS
  'Previsión de cobro; se rellena al pasar aeat_sif_estado a enviado_ok (baseline: vencimiento o emisión+30d).';

ALTER TABLE public.facturas
  ADD COLUMN IF NOT EXISTS aeat_sif_estado text;

CREATE OR REPLACE FUNCTION public.facturas_sync_fecha_estimada_cobro()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  v_base date;
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF NEW.aeat_sif_estado IS DISTINCT FROM OLD.aeat_sif_estado
       AND lower(trim(coalesce(NEW.aeat_sif_estado, ''))) = 'enviado_ok'
    THEN
      IF NEW.fecha_vencimiento IS NOT NULL THEN
        NEW.fecha_estimada_cobro := NEW.fecha_vencimiento;
      ELSE
        v_base := COALESCE(NEW.fecha_emision, NEW.fecha, NEW.fecha_factura, CURRENT_DATE);
        NEW.fecha_estimada_cobro := (v_base + INTERVAL '30 days')::date;
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_facturas_estimada_cobro_verifactu ON public.facturas;
CREATE TRIGGER trg_facturas_estimada_cobro_verifactu
  BEFORE UPDATE OF aeat_sif_estado ON public.facturas
  FOR EACH ROW
  EXECUTE FUNCTION public.facturas_sync_fecha_estimada_cobro();

COMMENT ON FUNCTION public.facturas_sync_fecha_estimada_cobro() IS
  'Si aeat_sif_estado pasa a enviado_ok, fija fecha_estimada_cobro (prioriza fecha_vencimiento).';

-- ─── POD: firma inline (base64) y URL de almacenamiento (bucket / CDN) ───────
ALTER TABLE public.portes
  ADD COLUMN IF NOT EXISTS firma_consignatario_b64 text,
  ADD COLUMN IF NOT EXISTS firma_consignatario_url text,
  ADD COLUMN IF NOT EXISTS nombre_consignatario_final text,
  ADD COLUMN IF NOT EXISTS fecha_entrega_real timestamptz,
  ADD COLUMN IF NOT EXISTS conductor_asignado_id uuid REFERENCES public.profiles (id) ON DELETE SET NULL;

COMMENT ON COLUMN public.portes.firma_consignatario_b64 IS
  'Firma PNG/SVG en Base64 (data URL o raw); alternativa a URL en bucket.';
COMMENT ON COLUMN public.portes.firma_consignatario_url IS
  'URL pública o firmada (p. ej. Storage) si la firma no va en fila.';
COMMENT ON COLUMN public.portes.nombre_consignatario_final IS 'Nombre de quien firma la entrega.';
COMMENT ON COLUMN public.portes.fecha_entrega_real IS 'Marca hora de la entrega confirmada.';
COMMENT ON COLUMN public.portes.conductor_asignado_id IS 'Perfil (profiles.id) conductor explícito.';

-- ─── Índices GIN (jsonb) para analítica / dashboard ───────────────────────────
CREATE INDEX IF NOT EXISTS idx_facturas_items_gin
  ON public.facturas USING GIN (items);

CREATE INDEX IF NOT EXISTS idx_facturas_datos_json_gin
  ON public.facturas USING GIN (datos_json);

CREATE INDEX IF NOT EXISTS idx_facturas_porte_lineas_snapshot_gin
  ON public.facturas USING GIN (porte_lineas_snapshot);

CREATE INDEX IF NOT EXISTS idx_audit_logs_old_data_gin
  ON public.audit_logs USING GIN (old_data)
  WHERE old_data IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_audit_logs_new_data_gin
  ON public.audit_logs USING GIN (new_data)
  WHERE new_data IS NOT NULL;

COMMENT ON INDEX idx_facturas_items_gin IS 'Búsqueda analítica en líneas JSON de factura.';
COMMENT ON INDEX idx_audit_logs_old_data_gin IS 'Filtros JSON en trazas de auditoría (old_data).';
