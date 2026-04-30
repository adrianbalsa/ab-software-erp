# Política de retención y borrado de datos — AB Logistics OS

**Versión:** 1.0  
**Fecha efectiva:** 2026-04-29  
**Owner:** Adrian (solo-founder)  
**Estado:** Aprobada para uso interno y remisión a clientes / comité DD (sujeto a revisión legal externa si el contrato lo exige).

## 1. Alcance y marco

Esta política complementa:

- `docs/legal/PRIVACY_POLICY.md` (RGPD, portabilidad y borrado tras rescisión).
- `docs/legal/DPA_DATA_PROCESSING_AGREEMENT.md` (instrucciones del Responsable).
- `docs/operations/BACKUP_S3_POLICY.md` y `docs/operations/DISASTER_RECOVERY.md` (ciclo de vida de copias).

**Ámbito:** datos tratados en la plataforma (multi-tenant), registros técnicos, copias de seguridad y derivados de cumplimiento (p. ej. trazabilidad fiscal).

## 2. Principios

1. **Minimización:** conservar solo el tiempo necesario para la finalidad o obligación legal.
2. **Separación por tenant:** el borrado operativo respeta el aislamiento por `empresa_id` / RLS.
3. **Inmutabilidad fiscal:** los registros sujetos a VeriFactu / normativa de facturación **no se alteran** salvo rectificación reglamentaria; la “supresión” frente al interesado se materializa mediante anonimización o cierre de cuenta conforme a procedimiento acordado, sin romper la cadena de integridad exigible.
4. **Residuos en backup:** el borrado en producción puede preceder en días al purgado en copias frías; los plazos de backup siguen `BACKUP_S3_POLICY.md`.

## 3. Plazos orientativos por categoría

| Categoría | Retención orientativa | Base | Acción al vencimiento |
|-----------|------------------------|------|------------------------|
| Datos operativos activos (portes, facturas en curso, usuarios) | Mientras dure el contrato + periodo de transición (véase PRIVACY §7) | Contrato / RGPD | Export si solicita cliente; borrado o anonimización según procedimiento |
| Facturas y metadatos fiscales sellados / cadena VeriFactu | Plazo legal aplicable (típicamente **4 años** y hasta **6 años** según normativa y práctica fiscal; confirmar con asesoría) | Ley General Tributaria y normativa mercantil | No borrado destructivo salvo instrucción legal expresa; bloqueo de acceso operativo |
| Logs de aplicación y auditoría técnica (`audit_logs`, trazas operativas) | **24 meses** salvo investigación abierta | Seguridad / DD | Purga automática o manual por job documentado |
| Sesiones de soporte / chat persistido (si aplica) | **24 meses** desde última actividad | Mejora producto / soporte | Borrado lógico o físico por tenant |
| Movimientos bancarios y conciliación | Mientras el cliente use el módulo + **5 años** si aplica conservación contable (orientativo; ajustar por jurisdicción) | Contabilidad / PSD2 | Anonimización de PII en conceptos si procede |
| Entornos no productivos (staging, demos) | **90 días** máximo para datos reales; preferir datos sintéticos | Minimización | Reset / borrado programado |

Los plazos legales prevalecen sobre la tabla; cualquier conflicto se documenta en ticket y en `docs/operations/INCIDENT_REGISTER.md` si afecta a plazos.

## 4. Procedimiento de borrado (alta nivel)

1. **Solicitud:** Responsable (cliente) o proceso interno de baja.
2. **Validación:** comprobar ausencia de litigios, requerimientos AEPD o retención legal activa.
3. **Ejecución:** scripts o flujos aprobados (Supabase / API admin); no borrado manual ad hoc en producción sin doble control.
4. **Verificación:** muestreo de tablas clave y ausencia de datos personales donde debió aplicarse anonimización.
5. **Evidencia:** acta breve (fecha, tenant, responsable, resultado) archivada fuera del git si el comité lo exige.

## 5. Revisión

Revisión **anual** o ante cambio material de proveedor / normativa. Registrar la revisión en el registro de incidentes / actas de gobierno si hubo cambios de plazo.

## 6. Aprobación

| Rol | Nombre | Firma / fecha |
|-----|--------|----------------|
| Dirección / solo-founder | Adrian | 2026-04-29 (versión repo) |

*Sustituir por firma manuscrita o PDF firmado en el expediente del comité si se exige formalidad adicional.*
