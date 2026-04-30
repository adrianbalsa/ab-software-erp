# Registro de incidentes y acciones correctivas (rolling 12 meses)

**Objetivo (DD §3.2):** mantener trazabilidad de incidentes de seguridad, disponibilidad o cumplimiento, y de las acciones correctivas, con **ventana mínima de 12 meses** hacia atrás desde la fecha de auditoría.

**Instrucciones:** añadir una fila por incidente cerrado (o por cluster si se agrupa). Eliminar o archivar filas **más antiguas de 12 meses** en esta tabla (copiar al histórico fuera del repo si la normativa exige conservación mayor).

| Fecha cierre (UTC) | ID | Severidad | Resumen | Causa raíz (breve) | Acción correctiva | Owner | Estado |
|--------------------|-----|-----------|---------|-------------------|-------------------|-------|--------|
| *(plantilla — sin incidentes P1 registrados en repo)* | — | — | — | — | — | — | — |

## Referencias

- Escalado y severidades: `docs/operations/ON_CALL_RUNBOOK.md`
- Runbook genérico: `docs/operations/runbook_v1.md`
- DR / pérdida de datos: `docs/operations/DISASTER_RECOVERY.md`

## Plantilla para nueva fila (copiar debajo de la tabla)

```text
| YYYY-MM-DD | INC-YYYY-NNN | P1/P2/P3 | … | … | … | nombre | cerrado |
```
