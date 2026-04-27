# Acta de handover operativo — plantilla

**Copiar a almacenamiento interno** (no en repositorio público con datos sensibles). Completar en **UTC**.

| Campo | Valor |
|--------|--------|
| Fecha y hora inicio / fin | |
| Entorno cubierto | Producción / Staging |
| Moderador | |
| Asistentes (nombre, rol, org) | |

## 1. Alcance reconocido

Los asistentes confirman haber recibido y revisado el paquete **`HANDOVER_PACKAGE.md`** y, como mínimo, los documentos marcados con **Sí**:

| Documento | Revisado (Sí/No) |
|-------------|-------------------|
| `OPS_001_TOPOLOGIA_PLATAFORMA.md` | |
| `ON_CALL_RUNBOOK.md` | |
| `DISASTER_RECOVERY.md` | |
| `VERIFACTU_OPERATIONS_RUNBOOK.md` | |
| `MONITORING_OBSERVABILITY.md` | |

## 2. Accesos y plataformas (sin anotar secretos)

Solo marcar **provisionado / verificado**; las credenciales viven en el gestor acordado (1Password, Vault, etc.).

| Sistema | Acceso verificado (Sí/No) | Notas |
|---------|---------------------------|--------|
| Railway (API + worker) | | |
| Vercel (frontend) | | |
| Supabase (dashboard + SQL) | | |
| GitHub org / Actions | | |
| AWS (S3 backups) | | |
| Stripe Dashboard | | |
| Sentry | | |
| DNS / registrador | | |

## 3. Prueba práctica (opcional pero recomendada)

| Prueba | Resultado (OK / N/A) |
|--------|------------------------|
| `GET /live` y `/health/deep` contra API productiva | |
| Simulacro de ticket P2 (documentado, sin impacto cliente) | |

## 4. Aceptación

Declaramos que el equipo receptor puede **clasificar y escalar** incidencias críticas usando los runbooks citados, y que los **owners** de la tabla en `HANDOVER_PACKAGE.md` quedan asignados o explícitamente pendientes con fecha.

| Rol | Nombre | Firma / Fecha |
|-----|--------|----------------|
| Entrega (emisor) | | |
| Recepción (lead operaciones) | | |
