-- Campo de emisiones simplificado para reportes financieros ESG.
alter table if exists public.portes
add column if not exists co2_kg numeric;

-- Backfill inicial desde campo legacy si existe valor.
update public.portes
set co2_kg = coalesce(co2_kg, co2_emitido)
where co2_kg is null;
