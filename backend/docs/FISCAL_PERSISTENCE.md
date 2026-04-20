# Persistencia fiscal (VeriFactu, inmutabilidad, soft delete)

## Migración

Aplicar `migrations/20260319_fiscal_immutability_soft_delete_snapshot.sql` en Supabase.

- **Facturas / auditoría**: trigger `enforce_immutable_when_hashed`: con `hash_registro` no vacío, no hay UPDATE ni DELETE salvo conexión **`service_role`** (p. ej. clave service del backend: compensación si falla el flujo tras insert).
- **Facturas**: columnas `porte_lineas_snapshot` (jsonb) y `total_km_estimados_snapshot`.
- **Portes / gastos / flota** (+ `vehiculos` si existe): `deleted_at`.

Si el trigger falla al crearse, en Postgres 14+ prueba `EXECUTE FUNCTION` en lugar de `EXECUTE PROCEDURE`.

## VeriFactu (código)

### Dos huellas SHA-256 (propósito distinto; no duplicar criterio en DD)

1. **Cadena DB emisión** (`hash_registro` / `hash_factura` / `huella_hash`): `generar_hash_factura_oficial(..., HUELLA_EMISION)` — pipe `num|fecha|NIF_emisor|total|hash_prev` (NIF emisor normalizado). Es la que usa `VerifactuService.generate_invoice_hash` al emitir F1/R1.
2. **Cadena auxiliar** (`fingerprint_hash` / `previous_fingerprint`): misma API con `HUELLA_FINGERPRINT` — pipe `NIF_emisor|NIF_receptor|num|fecha|total|hash_prev` (NIFs como en el legado de emisión; el receptor se resuelve desde `clientes` en auditorías REST).
3. **XML SuministroLR / presupuestos**: `VerifactuService.generar_hash_factura` — concatenación canónica distinta para el registro exportable AEAT; **no** sustituye a (1) ni (2).

Auditorías (`verify_invoice_chain`, `diagnose_fingerprint_hash_chain`) deben usar filas **materializadas** (`materialize_factura_rows_for_fingerprint_verify` + mapa NIF cliente) para coincidir con lo sellado en emisión.

### Configuración

Series de numeración: `Settings.VERIFACTU_SERIE_FACTURA` y `VERIFACTU_SERIE_RECTIFICATIVA` (env `VERIFACTU_SERIE_*`, por defecto `FAC` / `R`).

`VerifactuService.generar_hash_factura` (punto 3) usa cadena normalizada (NIF sin espacios y mayúsculas, fecha ISO, total con 2 decimales). El **siguiente secuencial** sale de la última fila de la empresa (orden `numero_secuencial` / `fecha_emision`).

Para **F1** desde portes, `hash_anterior` es el hash de esa última factura en cadena.

### Rectificativa R1 [cite: 2026-03-22]

- Migración: `migrations/20260323_facturas_rectificativas_r1.sql` (`factura_rectificada_id`, `motivo_rectificacion`).
- `FacturasService.emitir_factura_rectificativa`: solo **F1** sellada; importes negativos; `hash_anterior` del registro R1 = **`hash_registro` de la F1 rectificada**; `numero_secuencial` sigue siendo el siguiente global.
- La huella añade segmentos opcionales `|T:R1|` y `|RECT:<número original>|` antes del hex del hash anterior (las emisiones F1 sin esos campos conservan el hash histórico).

## Soft delete

Helpers: `app.db.soft_delete` o reexport `app.db.base_class`. Listados usan `filter_not_deleted(...)`.
