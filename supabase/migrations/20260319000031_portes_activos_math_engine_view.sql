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
