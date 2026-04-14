-- 003_esg_factors.sql
-- ESG factors catalog for route-level CO2 estimation.

create table if not exists public.factores_emision (
    id uuid primary key default gen_random_uuid(),
    tipo_vehiculo varchar(120) not null,
    normativa varchar(40) not null,
    factor_co2_km double precision not null,
    created_at timestamptz not null default now()
);

create unique index if not exists ux_factores_emision_tipo_normativa
    on public.factores_emision (tipo_vehiculo, normativa);

insert into public.factores_emision (tipo_vehiculo, normativa, factor_co2_km)
values
    ('Articulado > 40t', 'Euro VI', 750.0),
    ('Rigido 12-24t', 'Euro VI', 540.0),
    ('Furgoneta LCV', 'Euro 6', 190.0)
on conflict (tipo_vehiculo, normativa) do update
set factor_co2_km = excluded.factor_co2_km;
