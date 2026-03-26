-- Encadenamiento adicional de integridad (fingerprint_hash + previous_fingerprint)
alter table if exists public.facturas
add column if not exists fingerprint_hash text,
add column if not exists previous_fingerprint text;

create index if not exists idx_facturas_empresa_fingerprint_hash
  on public.facturas (empresa_id, fingerprint_hash);

-- Trigger de inmutabilidad reforzada:
-- si ya existe fingerprint_hash, no se permiten updates (excepto transición de finalización ya permitida).
create or replace function public.enforce_immutable_facturas()
returns trigger
language plpgsql
as $$
begin
  if current_setting('role', true) = 'service_role' then
    if tg_op = 'DELETE' then
      return old;
    end if;
    return new;
  end if;

  if tg_op = 'UPDATE' then
    if old.hash_registro is not null
       and length(trim(old.hash_registro::text)) > 0
       and coalesce(old.is_finalized, false) is false
       and coalesce(new.is_finalized, false) is true
       and new.fingerprint is not null
       and length(trim(new.fingerprint::text)) > 0
    then
      return new;
    end if;

    if old.fingerprint_hash is not null and length(trim(old.fingerprint_hash::text)) > 0 then
      raise exception 'FORBIDDEN_IMMUTABLE_FACTURA: UPDATE prohibido (fingerprint_hash ya fijado)';
    end if;

    if old.hash_registro is not null and length(trim(old.hash_registro::text)) > 0 then
      raise exception
        'IMMUTABLE_ROW: UPDATE prohibido una vez fijado hash_registro (tabla facturas)';
    end if;
    return new;
  elsif tg_op = 'DELETE' then
    if coalesce(old.is_finalized, false) is true then
      raise exception
        'IMMUTABLE_ROW: DELETE prohibido para factura finalizada VeriFactu (tabla facturas)';
    end if;
    if old.hash_registro is not null and length(trim(old.hash_registro::text)) > 0 then
      raise exception
        'IMMUTABLE_ROW: DELETE prohibido una vez fijado hash_registro (tabla facturas)';
    end if;
    return old;
  end if;

  return coalesce(new, old);
end;
$$;
