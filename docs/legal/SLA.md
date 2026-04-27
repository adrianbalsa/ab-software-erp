# SLA (Service Level Agreement) — AB Logistics OS

**Versión:** 1.1
**Última actualización:** 26/04/2026
**Jurisdicción:** España

## 1. Alcance
Este SLA aplica a la prestación del servicio SaaS de AB Logistics OS y cubre la disponibilidad de la Plataforma en la topología oficial de producción documentada: frontend en Vercel, API y worker en Railway, Redis en Railway, base de datos PostgreSQL en Supabase o Railway y backups externos en S3 en región UE.

Quedan excluidos servicios, integraciones y componentes de terceros cuando no estén bajo control directo de AB Logistics OS, incluyendo, entre otros, Vercel, Railway, Supabase, AWS S3, proveedores de DNS, correo, pagos, mapas, IA/OCR y servicios de administración tributaria.

## 2. Definiciones
- **Uptime mensual:** porcentaje de tiempo en que la Plataforma se considera “disponible” dentro del periodo mensual de medición.  
- **Ventanas de mantenimiento programadas:** periodos planificados con el objetivo de realizar mantenimiento preventivo o actualizaciones.  
- **Disponibilidad:** se entiende como accesibilidad del servicio principal a través de los endpoints publicados y verificados mediante los mecanismos de health-check y monitorización operativa.
- **RPO (Recovery Point Objective):** antigüedad máxima objetivo de los datos recuperables tras un incidente con pérdida o corrupción de datos.
- **RTO (Recovery Time Objective):** tiempo objetivo para restaurar una capacidad operativa mínima desde que AB Logistics OS confirma el incidente, dispone de acceso administrativo a los proveedores afectados y activa el procedimiento de recuperación.

## 3. Disponibilidad (Uptime)
AB Logistics OS se compromete a una disponibilidad mensual del **99,5%** para el servicio SaaS en su conjunto (“**Compromiso de Disponibilidad**”), medida sobre los endpoints públicos de producción y excluyendo las circunstancias indicadas en este SLA.

El objetivo operativo interno es mantener la disponibilidad lo más cercana posible al **99,9%**, apoyándose en los SLA propios de Vercel, Railway, Supabase y AWS. No obstante, la arquitectura actual no declara una plataforma propia multi-región activa-activa, por lo que el compromiso contractual queda limitado al umbral anterior salvo pacto expreso en el contrato comercial.

### Exclusiones
Se excluyen del cálculo de uptime:
1. Ventanas de mantenimiento programadas previamente notificadas o razonablemente esperables.
2. Periodos atribuibles a fuerza mayor o a terceros no controlados (p. ej., caídas de Vercel, Railway, Supabase, AWS, DNS u otros proveedores externos cuando no sean imputables a AB Logistics OS).
3. Incidencias derivadas de configuraciones o integración del Cliente no conforme a documentación.
4. Interrupciones causadas por cambios, credenciales, cuotas, dominios, DNS o permisos gestionados por el Cliente.
5. Degradación de funcionalidades opcionales dependientes de terceros, siempre que el núcleo de la Plataforma siga disponible.

### Ventana de mantenimiento programado
- **Domingos, de 02:00 a 05:00 CET**, salvo que se acuerde una franja alternativa por escrito.  

## 4. Resiliencia (RPO / RTO)
La resiliencia se basa en la infraestructura real documentada en `docs/INFRASTRUCTURE.md`, `docs/operations/OPS_001_TOPOLOGIA_PLATAFORMA.md`, `docs/operations/DISASTER_RECOVERY.md` y `docs/operations/BACKUP_S3_POLICY.md`:

- Producción oficial en Vercel/Railway.
- PostgreSQL en Supabase o Railway, según el entorno contratado.
- Redis en Railway para ARQ, rate limiting y caches operativas.
- Backup lógico diario de base de datos vía GitHub Actions, con subida a S3 en región UE y cifrado SSE-S3 o SSE-KMS.
- Smoke test de restore semanal o manual sobre Postgres efímero.

### Objetivos por escenario

| Escenario | RPO objetivo | RTO objetivo | Alcance |
|-----------|--------------|--------------|---------|
| Redeploy de frontend, API o worker sin pérdida de datos | No aplica | **4 horas** | Restaurar servicio desde Vercel/Railway, variables y healthchecks. |
| Incidente de Redis sin pérdida de datos transaccionales | No aplica para PostgreSQL | **8 horas** | Restablecer colas, rate limiting y jobs pendientes según capacidad del proveedor. |
| Caída o degradación de proveedor principal | Según proveedor afectado | **12 horas** | Mitigación, cambio de configuración o workaround razonable si existe alternativa operativa. |
| Corrupción o pérdida de base de datos con restore desde backup S3 | **24 horas** desde el último backup diario correcto | **24 horas** | Restauración de `schema.sql` y `public_data.sql`, validación funcional y reapertura controlada del servicio. |
| Incidente catastrófico con recreación completa de entorno | **24 horas** desde el último backup diario correcto | **48 horas** | Reprovisión de servicios, variables, dominios, base de datos, Redis, API, worker y frontend. |

Estos objetivos son compromisos de recuperación razonable, no garantías absolutas. Dependen de la disponibilidad de credenciales, permisos administrativos, proveedores externos, backups válidos y ausencia de restricciones legales, de seguridad o de integridad que obliguen a mantener el servicio cerrado durante la investigación.

### Backups y evidencia

- El backup de base de datos se ejecuta diariamente a las **03:00 UTC** mediante GitHub Actions.
- Los backups deben almacenarse en S3 en región AWS Europa (`eu-*`) y con cifrado server-side.
- La restauración se valida mediante workflow semanal de smoke restore o ejecución manual documentada.
- El RPO se considera cumplido si existe un backup diario correcto, cifrado y restaurable dentro de las últimas 24 horas.

## 5. Matriz de soporte y tiempos de respuesta
Los tiempos se miden desde el momento en que el Cliente notifica formalmente la incidencia por los canales acordados:
- **Nivel Crítico:** caída del sistema / fallo VeriFactu que impida operación < **4 horas**.  
- **Nivel Alto:** degradación relevante de funcionalidad o bloqueo parcial < **12 horas**.  
- **Nivel Normal:** incidencias menores o mejoras < **48 horas**.

AB Logistics OS realizará esfuerzos razonables para mitigar el impacto, ofreciendo workarounds cuando sea viable.

## 6. Penalizaciones por incumplimiento (créditos de servicio)
En caso de incumplimiento del Compromiso de Disponibilidad en un periodo de facturación, la compensación se realizará **exclusivamente** mediante **créditos de servicio** para futuras facturas del Cliente.

### Exclusión de cash refunds
Las partes acuerdan expresamente que **no** procederán devoluciones en efectivo (“**cash refunds**”) como mecanismo de compensación.

### Forma y cálculo de compensación (a modo de referencia)
- Si el uptime mensual se sitúa en el rango **[99,5% - 99,0%)**, la compensación se otorgará como **créditos equivalentes a un porcentaje del importe mensual de los Servicios** acordados.
- Si el uptime mensual es inferior a **99,0%**, la compensación se incrementará conforme al mecanismo de créditos acordado en el contrato.

*(El cálculo final exacto, el porcentaje aplicable y las condiciones de elegibilidad se especificarán en el contrato comercial o Anexo de SLA.)*

