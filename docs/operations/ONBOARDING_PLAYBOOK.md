# Onboarding de producto (2 semanas) — AB Logistics OS

Playbook operativo para activar nuevas empresas sin tocar el roadmap técnico ya cerrado.
Este documento cubre onboarding comercial/ops (no onboarding de desarrollo).

## Objetivo y alcance

- Reducir tiempo a valor (TTV) desde alta hasta primer uso real.
- Estandarizar activación de cuenta, cobro, primer flujo de negocio y handoff a soporte.
- Medir fricción por paso para iterar sin cambios ad-hoc.

No incluye:

- Desarrollo de app móvil (fase 4 del roadmap principal).
- Cambios de arquitectura de backend.

## Definición de "activado"

Una empresa queda activada cuando completa los siguientes hitos:

- Alta administrativa y acceso inicial con usuario admin.
- Método de pago operativo (Stripe/mandato según caso).
- Primer flujo de negocio ejecutado (p. ej. primer porte o primera factura).
- Confirmación de acceso al portal cliente y módulo de ayuda.

## Roles y ownership

- Product owner: decide prioridades, bloquea cambios fuera de alcance.
- Ops / Customer success: ejecuta checklist con cliente y seguimiento diario.
- Soporte técnico: resuelve incidencias funcionales y de acceso.
- Engineering on-call: solo para bloqueos de plataforma o bugs críticos.

## Plan de ejecución (10 días hábiles)

## Semana 1 — Activación base y primer valor

### Día 1 — Kickoff interno + preparación de cuenta

- Crear ficha de onboarding (empresa, contacto, plan, fecha objetivo de go-live).
- Confirmar entorno y URLs públicas correctas.
- Validar variables operativas mínimas en producción:
  - `PUBLIC_APP_URL`
  - `NEXT_PUBLIC_SUPPORT_EMAIL`
  - `SECURITY_CONTACT_EMAIL`
- Revisar disponibilidad del runbook de billing (`docs/operations/STRIPE_BILLING.md`).

Entregable:

- Ficha de cliente creada y checklist inicial asignado.

### Día 2 — Alta y acceso admin

- Alta de usuario admin y verificación de login.
- Confirmar recuperación de contraseña y acceso al dashboard.
- Recorrido guiado de "primeros pasos" desde Help Center.

Entregable:

- Admin con acceso validado y primera sesión completa.

### Día 3 — Cobro y plan

- Ejecutar setup de plan y billing (según runbook de Stripe).
- Validar que el estado de plan y referencias de suscripción están sincronizados.
- Confirmar vía soporte que la empresa entiende ciclo de cobro/facturación.

Entregable:

- Método de pago activo y plan confirmado.

### Día 4 — Primer flujo operativo guiado

- Elegir un flujo principal por cliente:
  - flujo A: primer porte completo, o
  - flujo B: primera factura ERP.
- Acompañar ejecución end-to-end (input, procesamiento, resultado visible).
- Registrar fricciones detectadas en pasos y UX.

Entregable:

- Primer resultado de negocio generado en plataforma.

### Día 5 — Cierre semana 1

- Revisión interna de bloqueos y tiempos por paso.
- Crear lista de acciones para semana 2 (quick wins de proceso/documentación).
- Confirmar fecha objetivo de go-live con cliente.

Entregable:

- Estado semáforo por cliente: verde/amarillo/rojo.

## Semana 2 — Escalado controlado y handoff

### Día 6 — Formación operativa corta

- Sesión de 30-45 min para usuarios clave (operación/administración).
- Repaso de módulos, alertas y rutas de soporte.
- Entrega de material mínimo:
  - guía de primeros pasos
  - enlace a `/help`
  - política de privacidad y SLA

Entregable:

- Usuarios clave formados y confirmación de recepción de materiales.

### Día 7 — Validación de autoservicio

- El cliente ejecuta un flujo sin acompañamiento.
- Soporte observa solo con intervención bajo demanda.
- Medir si completa sin bloqueos críticos.

Entregable:

- Evidencia de uso autónomo.

### Día 8 — Calidad de servicio y soporte

- Simular incidencia leve y verificar circuito de soporte.
- Confirmar tiempos de primera respuesta y resolución.
- Ajustar macros/checklists de soporte si hay fricción repetida.

Entregable:

- Circuito de soporte validado.

### Día 9 — Pre-go-live checklist final

- Revisión final de seguridad/compliance visibles al cliente:
  - endpoint público de compliance
  - contacto de seguridad
  - documentación legal publicada
- Validar contratos operativos aplicables (API estable en `/api/v1/` para integraciones nuevas).
- Confirmar ausencia de bloqueos abiertos críticos.

Entregable:

- Checklist de go-live completo.

### Día 10 — Go-live + handoff

- Confirmación formal de activación.
- Asignar ownership a operación continua (Customer Success + Soporte).
- Programar revisión de salud a 7 y 30 días.

Entregable:

- Cliente en operación continua con seguimiento programado.

## KPIs de onboarding (mínimo)

- Tiempo a primer login exitoso (horas).
- Tiempo a primer valor (días).
- Tasa de finalización onboarding (%).
- Drop-off por paso (% por etapa).
- Tickets de soporte en primeros 14 días (número y categoría).
- Tiempo medio de primera respuesta de soporte.

## Criterio de go-live

Go-live permitido solo si:

- El usuario admin opera sin bloqueo crítico.
- Billing está activo y verificado.
- Existe al menos un flujo de negocio completo en producción.
- El cliente conoce canal de soporte y Help Center.

Si alguno falla, el estado permanece en "pilotando" y se aplica plan de mitigación de 48h.

## Cadencia operativa recomendada

- Daily interno de 15 min durante las 2 semanas.
- Actualización al cliente cada 48h durante semana 1.
- Actualización al cliente cada 72h durante semana 2.
- Revisión ejecutiva semanal con estado y riesgos.

## Riesgos comunes y mitigación

- Acceso/credenciales no completadas a tiempo.
  - Mitigación: checklist de acceso en día 1 y fallback de soporte.
- Dudas de facturación/cobro bloquean adopción.
  - Mitigación: resolver billing en día 3, no al final.
- Entrenamiento insuficiente de usuarios clave.
  - Mitigación: sesión corta obligatoria + prueba autónoma en día 7.
- Escalado prematuro con proceso no estabilizado.
  - Mitigación: piloto con pocas cuentas activas en paralelo antes de ampliar.

## Referencias del repositorio

- `SCRATCHPAD.md` (estado del roadmap y alcance cerrado/no cerrado).
- `docs/operations/STRIPE_BILLING.md` (runbook de billing).
- `docs/operations/ONBOARDING_CLIENT_TEMPLATE.md` (plantilla rellenable por cuenta).
- `docs/operations/ONBOARDING_CLIENT_EXAMPLE.md` (ejemplo pre-rellenado con datos ficticios).
- `docs/PLATFORM_CONTRACTS.md` (contratos de plataforma e integraciones).
- `README_SECURITY.md` (postura y operación de secretos).
- `docs/legal/PRIVACY_POLICY.md`
- `docs/legal/SLA.md`
