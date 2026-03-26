# SLA (Service Level Agreement) — AB Logistics OS

**Versión:** 1.0  
**Última actualización:** 25/03/2026  
**Jurisdicción:** España

## 1. Alcance
Este SLA aplica a la prestación del servicio SaaS de AB Logistics OS y cubre la disponibilidad de la Plataforma, excluyendo servicios, integraciones y componentes de terceros cuando dichos componentes no estén bajo control directo de AB Logistics OS.

## 2. Definiciones
- **Uptime mensual:** porcentaje de tiempo en que la Plataforma se considera “disponible” dentro del periodo mensual de medición.  
- **Ventanas de mantenimiento programadas:** periodos planificados con el objetivo de realizar mantenimiento preventivo o actualizaciones.  
- **Disponibilidad:** se entiende como accesibilidad del servicio principal a través de los endpoints publicados y verificados mediante los mecanismos de health-check y monitorización operativa.

## 3. Disponibilidad (Uptime)
AB Logistics OS se compromete a una disponibilidad mensual del **99,9%** (“**Compromiso de Disponibilidad**”).

### Exclusiones
Se excluyen del cálculo de uptime:
1. Ventanas de mantenimiento programadas previamente notificadas o razonablemente esperables.
2. Periodos atribuibles a fuerza mayor o a terceros no controlados (p. ej., caídas de proveedores de infraestructura ajenos cuando no sea imputable a AB Logistics OS).
3. Incidencias derivadas de configuraciones o integración del Cliente no conforme a documentación.

### Ventana de mantenimiento programado
- **Domingos, de 02:00 a 05:00 CET**, salvo que se acuerde una franja alternativa por escrito.  

## 4. Resiliencia (RPO / RTO)
Basado en la infraestructura y el sistema de copias de seguridad y restauración definido para producción:
- **RPO (Recovery Point Objective): 24 horas**  
  (capacidad de recuperar el estado aproximado de los datos hasta el último punto de copia disponible, incluyendo copias off-site diarias).
- **RTO (Recovery Time Objective): 12 horas**  
  (tiempo objetivo para restablecer la operación del servicio tras un incidente catastrófico, una vez activado el procedimiento de recuperación).

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
- Si el uptime mensual se sitúa en el rango **[99,9% - 99,5%)**, la compensación se otorgará como **créditos equivalentes a un porcentaje del importe mensual de los Servicios** acordados.  
- Si el uptime mensual es inferior a **99,5%**, la compensación se incrementará conforme al mecanismo de créditos acordado en el contrato.  

*(El cálculo final exacto, el porcentaje aplicable y las condiciones de elegibilidad se especificarán en el contrato comercial o Anexo de SLA.)*

