-- ESG CO2 module aligned with Euro VI fleet standards.

create table if not exists public.estandares_emision_flota (
    id uuid primary key default gen_random_uuid(),
    categoria_vehiculo text not null,
    segmento_mma text not null,
    factor_emision_kg_km numeric(10,6) not null check (factor_emision_kg_km >= 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (categoria_vehiculo, segmento_mma)
);

insert into public.estandares_emision_flota (categoria_vehiculo, segmento_mma, factor_emision_kg_km)
values
    ('Ligero', '<3.5t', 0.21),
    ('Rígido Pequeño', '3.5t-7.5t', 0.50),
    ('Rígido Grande', '7.5t-16t', 0.68),
    ('Articulado', '>33t', 0.95)
on conflict (categoria_vehiculo, segmento_mma) do update
set
    factor_emision_kg_km = excluded.factor_emision_kg_km,
    updated_at = now();

alter table if exists public.portes
add column if not exists co2_kg numeric(14,6),
add column if not exists factor_emision_aplicado numeric(10,6);
