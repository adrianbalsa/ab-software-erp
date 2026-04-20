-- Fase 4.4 consolidación: integridad financiera en gastos
-- - `porte_id` (FK opcional a public.portes)
-- - `categoria` normalizada como enum

do $$
begin
  if not exists (
    select 1
    from pg_type
    where typname = 'gasto_categoria_enum'
  ) then
    create type public.gasto_categoria_enum as enum (
      'combustible',
      'materiales',
      'servicios',
      'otros'
    );
  end if;
end$$;

alter table public.gastos
  add column if not exists porte_id uuid;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'gastos_porte_id_fkey'
      and conrelid = 'public.gastos'::regclass
  ) then
    alter table public.gastos
      add constraint gastos_porte_id_fkey
      foreign key (porte_id) references public.portes(id)
      on update cascade
      on delete set null;
  end if;
end$$;

-- Si `categoria` no existe, se crea como enum.
alter table public.gastos
  add column if not exists categoria public.gasto_categoria_enum;

-- Si `categoria` existe pero no es enum, se convierte preservando datos.
do $$
declare
  current_type text;
begin
  select t.typname
    into current_type
  from pg_attribute a
  join pg_class c on c.oid = a.attrelid
  join pg_namespace n on n.oid = c.relnamespace
  join pg_type t on t.oid = a.atttypid
  where n.nspname = 'public'
    and c.relname = 'gastos'
    and a.attname = 'categoria'
    and not a.attisdropped
    and a.attnum > 0;

  if current_type is distinct from 'gasto_categoria_enum' then
    alter table public.gastos
      alter column categoria type public.gasto_categoria_enum
      using (
        case lower(coalesce(categoria::text, ''))
          when 'combustible' then 'combustible'::public.gasto_categoria_enum
          when 'materiales' then 'materiales'::public.gasto_categoria_enum
          when 'servicios' then 'servicios'::public.gasto_categoria_enum
          else 'otros'::public.gasto_categoria_enum
        end
      );
  end if;
end$$;

alter table public.gastos
  alter column categoria set default 'otros'::public.gasto_categoria_enum;

update public.gastos
set categoria = 'otros'::public.gasto_categoria_enum
where categoria is null;

alter table public.gastos
  alter column categoria set not null;

create index if not exists idx_gastos_empresa_porte_fecha
  on public.gastos (empresa_id, porte_id, fecha desc);
