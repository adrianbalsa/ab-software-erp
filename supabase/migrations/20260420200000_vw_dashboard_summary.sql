-- Vista agregada para KPIs del dashboard (owner): una fila por empresa con actividad visible (RLS).
-- No usa FROM empresas para evitar enumerar IDs ajenos si la tabla empresas no tuviera RLS.
-- Sustituye múltiples SELECT desde la app; el mes corriente usa CURRENT_DATE en el servidor DB.
-- EBITDA en API se recalcula con round_fiat sobre ingresos/gastos (coherencia Math Engine).

CREATE OR REPLACE VIEW public.vw_dashboard_summary AS
WITH month_bounds AS (
  SELECT DATE_TRUNC('month', (CURRENT_DATE)::timestamp)::date AS month_start,
         (DATE_TRUNC('month', (CURRENT_DATE)::timestamp) + INTERVAL '1 month')::date AS month_next
),
ing AS (
  SELECT
    f.empresa_id,
    SUM(COALESCE(f.total_factura, 0))::numeric AS ingresos_total
  FROM public.facturas f
  GROUP BY f.empresa_id
),
gas AS (
  SELECT
    g.empresa_id,
    SUM(COALESCE(g.total_eur, g.total_chf, 0))::numeric AS gastos_total
  FROM public.gastos g
  WHERE g.deleted_at IS NULL
  GROUP BY g.empresa_id
),
pend AS (
  SELECT
    p.empresa_id,
    SUM(COALESCE(p.precio_pactado, 0))::numeric AS pendientes_cobro
  FROM public.portes p
  WHERE p.deleted_at IS NULL
    AND p.estado = 'pendiente'
  GROUP BY p.empresa_id
),
mes AS (
  SELECT
    p.empresa_id,
    SUM(COALESCE(p.km_estimados, 0))::numeric AS km_totales_mes,
    SUM(COALESCE(p.bultos, 0))::bigint AS bultos_mes
  FROM public.portes p
  CROSS JOIN month_bounds b
  WHERE p.deleted_at IS NULL
    AND p.fecha >= b.month_start
    AND p.fecha < b.month_next
  GROUP BY p.empresa_id
),
emp_keys AS (
  SELECT empresa_id FROM ing
  UNION
  SELECT empresa_id FROM gas
  UNION
  SELECT empresa_id FROM pend
  UNION
  SELECT empresa_id FROM mes
)
SELECT
  k.empresa_id,
  COALESCE(ing.ingresos_total, 0)::numeric AS ingresos_total,
  COALESCE(gas.gastos_total, 0)::numeric AS gastos_total,
  COALESCE(pend.pendientes_cobro, 0)::numeric AS pendientes_cobro,
  COALESCE(mes.km_totales_mes, 0)::numeric AS km_totales_mes,
  COALESCE(mes.bultos_mes, 0)::bigint AS bultos_mes
FROM emp_keys k
LEFT JOIN ing ON ing.empresa_id = k.empresa_id
LEFT JOIN gas ON gas.empresa_id = k.empresa_id
LEFT JOIN pend ON pend.empresa_id = k.empresa_id
LEFT JOIN mes ON mes.empresa_id = k.empresa_id;

COMMENT ON VIEW public.vw_dashboard_summary IS
  'Agregados por empresa (solo filas con actividad visible vía RLS): ingresos, gastos, pendiente cobro, km/bultos mes calendario actual (CURRENT_DATE).';
