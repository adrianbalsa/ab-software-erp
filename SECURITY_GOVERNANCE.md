# Security Governance: DDL Hardening

Este endurecimiento añade una capa de defensa en profundidad a nivel de motor de base de datos para `public.facturas` y `public.auditoria`.

## Que riesgo mitigamos

Si un atacante consigue una `SUPABASE_KEY` del backend y logra actuar como rol de aplicacion (`authenticated` o `service_role`), **no puede auto-sabotear la historia fiscal** mediante DDL destructivo sobre estas tablas.

## Controles aplicados

- `REVOKE TRUNCATE` impide borrado masivo de registros fiscales.
- `REVOKE TRIGGER` evita desactivar o reemplazar triggers de inmutabilidad.
- `REVOKE ALL ON SCHEMA extensions` reduce superficie para abusar de extensiones desde roles de aplicacion.

## Resultado de seguridad

La alteracion estructural o destructiva queda reservada a roles privilegiados fuera del alcance normal del backend (administracion/superuser).  
Incluso con una key comprometida de aplicacion, la base de datos mantiene el historial fiscal protegido por controles de privilegios nativos.
