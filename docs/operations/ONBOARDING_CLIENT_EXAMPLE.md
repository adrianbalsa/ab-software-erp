# Ejemplo de onboarding por cliente (datos ficticios) — AB Logistics OS

Ejemplo práctico basado en `docs/operations/ONBOARDING_CLIENT_TEMPLATE.md`.
Todos los datos de empresa, usuarios y fechas son ficticios.

## 0) Ficha del cliente

- Empresa: `Transportes Demo Levante S.L.`
- Segmento: `PYME transporte terrestre nacional`
- Plan contratado: `Pro`
- Contacto principal (nombre/email/teléfono): `Lucía Pérez` / `lucia.perez@demo-levante.example` / `+34 600 123 123`
- Fecha de inicio onboarding: `2026-04-21`
- Fecha objetivo de go-live: `2026-05-05`
- Owner Ops / CS: `Marta Ruiz`
- Owner Soporte: `Javier Gómez`
- Owner Producto: `Adrián Balsa`
- Estado actual: `go_live`

## 1) Checklist de activación (criterio "empresa activada")

- [x] Usuario admin creado y login validado.
- [x] Método de pago operativo (Stripe/mandato, según aplique).
- [x] Primer flujo de negocio ejecutado de extremo a extremo.
- [x] Acceso al portal cliente validado.
- [x] Cliente conoce canal de soporte y Help Center.

Notas:

- Cuenta activada en plazo. Sin incidencias de plataforma críticas.

## 2) Plan día a día (10 días hábiles)

## Semana 1

### Día 1 — Kickoff y preparación

- [x] Ficha completa y owners confirmados.
- [x] Variables operativas revisadas (`PUBLIC_APP_URL`, `NEXT_PUBLIC_SUPPORT_EMAIL`, `SECURITY_CONTACT_EMAIL`).
- [x] Runbook de billing revisado (`docs/operations/STRIPE_BILLING.md`).

Resultado del día:

- Kickoff completado con cliente; fecha objetivo validada.

Bloqueos:

- Ninguno.

### Día 2 — Alta y acceso admin

- [x] Alta admin completada.
- [x] Login y recovery validados.
- [x] Recorrido de primeros pasos realizado.

Resultado del día:

- Usuario admin operativo y primer acceso a dashboard confirmado.

Bloqueos:

- Ninguno.

### Día 3 — Cobro y plan

- [x] Configuración de plan y cobro completada.
- [x] Sincronización de plan/suscripción validada.
- [x] Cliente entiende ciclo de cobro/facturación.

Resultado del día:

- Billing activo en modo producción para la cuenta.

Bloqueos:

- Retraso de 2h en validación del método de pago por parte del cliente.

### Día 4 — Primer flujo operativo guiado

Flujo elegido:

- [x] A: primer porte completo
- [ ] B: primera factura ERP

Ejecución:

- [x] Flujo end-to-end completado.
- [x] Fricciones registradas (paso, síntoma, impacto).

Resultado del día:

- Primer porte completado y visible en trazabilidad.

Bloqueos:

- Duda de nomenclatura en campos de carga/descarga (resuelto con guía).

### Día 5 — Cierre de semana 1

- [x] Revisión de tiempos y fricciones.
- [x] Lista de acciones semana 2 definida.
- [x] Fecha objetivo de go-live revalidada con cliente.

Semáforo:

- [x] Verde
- [ ] Amarillo
- [ ] Rojo

Comentario de cierre semana:

- Progreso según plan, sin riesgos críticos abiertos.

## Semana 2

### Día 6 — Formación operativa

- [x] Sesión 30-45 min completada.
- [x] Material entregado (help, privacidad, SLA).
- [x] Confirmación de recepción por parte del cliente.

Resultado del día:

- Equipo de operaciones del cliente formado y con acceso a materiales.

Bloqueos:

- Ninguno.

### Día 7 — Validación autoservicio

- [x] Cliente ejecuta flujo sin acompañamiento.
- [x] Soporte interviene solo bajo demanda.
- [x] Resultado autónomo sin bloqueo crítico.

Resultado del día:

- Flujo autónomo completado en primer intento.

Bloqueos:

- Ninguno.

### Día 8 — Calidad de soporte

- [x] Simulación de incidencia leve realizada.
- [x] Tiempos de respuesta/solución medidos.
- [x] Ajustes de macro/checklist aplicados.

Resultado del día:

- Soporte respondió en 18 min; resolución en 46 min.

Bloqueos:

- Ninguno.

### Día 9 — Pre-go-live

- [x] Compliance público visible validado.
- [x] Contacto de seguridad visible y correcto.
- [x] Documentación legal publicada revisada.
- [x] Sin bloqueos críticos abiertos.

Resultado del día:

- Checklist pre-go-live cerrado al 100%.

Bloqueos:

- Ninguno.

### Día 10 — Go-live y handoff

- [x] Activación formal confirmada.
- [x] Handoff a operación continua completado.
- [x] Revisiones 7/30 días agendadas.

Resultado del día:

- Cuenta en operación continua.

Bloqueos:

- Ninguno.

## 3) Registro de riesgos y mitigaciones

| Fecha | Riesgo | Impacto | Mitigación | Owner | Estado |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-04-23 | Retraso del cliente al validar método de pago | Medio | Recordatorio y ventana extra de validación el mismo día | Marta Ruiz | Cerrado |
| 2026-04-24 | Confusión en campos del flujo de portes | Bajo | Mini-guía de campos + walkthrough de 10 min | Javier Gómez | Cerrado |

## 4) KPIs del onboarding de esta cuenta

- TTV a primer login (horas): `6`
- TTV a primer valor (días): `4`
- Tasa de finalización onboarding (%): `100`
- Drop-off principal (paso y %): `Paso billing (intento inicial): 10%`
- Tickets primeros 14 días (número): `3`
- Tiempo medio primera respuesta (min): `21`

## 5) Decisión final de estado

- Estado final:
  - [x] `go_live`
  - [ ] `pilotando`
  - [ ] `bloqueado`
- Justificación: onboarding completado sin bloqueos críticos y uso autónomo validado.
- Próxima revisión (fecha): `2026-05-12` (D+7) y `2026-06-04` (D+30)

## 6) Historial de cambios

| Fecha | Cambio | Autor |
| :--- | :--- | :--- |
| 2026-04-20 | Creación de ejemplo pre-rellenado | Codex |
