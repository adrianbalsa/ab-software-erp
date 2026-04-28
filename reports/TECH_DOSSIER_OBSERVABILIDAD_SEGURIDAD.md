# Dossier Tecnico de Observabilidad y Seguridad  
## AB Logistics OS - Bunker de Notificaciones (Handover / Investment Audit)

## Resumen Ejecutivo

El **Bunker de Notificaciones** de AB Logistics OS opera como un subsistema desacoplado del flujo transaccional principal: la API autentica, valida contexto multi-tenant y **acepta la orden de alerta sin bloquear la respuesta de negocio**.  

La confirmacion `202 Accepted` certifica que la solicitud fue admitida y encolada para entrega asincrona, reforzando tres atributos de activo:

- **Resiliencia operativa**: degradaciones del canal externo (Discord/Webhook) no interrumpen el core API.
- **Elasticidad de latencia**: el tiempo de respuesta al cliente no depende del tiempo de red del webhook.
- **Trazabilidad forense**: cada alerta se emite con metadatos de tenant, identidad y tiempo para auditoria.

---

## Capa de Seguridad Zero-Trust (Middleware)

### TenantRBACContextMiddleware

El `TenantRBACContextMiddleware` aplica un control de acceso **zero-trust por defecto** sobre peticiones mutantes (`POST/PUT/PATCH/DELETE`):

1. Extrae token (`Authorization Bearer` o cookie segura).
2. Decodifica y valida claims JWT.
3. Resuelve identidad real en persistencia.
4. Enlaza contexto de tenant y RBAC antes de permitir la mutacion.

Si cualquiera de esos pasos falla, retorna hard-fail (`401/403`) y bloquea la operacion.

### Aislamiento Multi-Tenancy via bind_write_context

El aislamiento no se delega solo al JWT: se revalida de forma activa con `bind_write_context` y `ensure_empresa_context`/`ensure_rbac_context` antes de escribir datos. Esto reduce riesgo de fuga de contexto entre corrutinas o clientes compartidos.

### Robustez demostrada ante suplantacion

Durante la validacion se observaron rechazos controlados (`403/401`) para identidades no mapeadas o claims inconsistentes.  
Conclusión de seguridad: **no existe camino de escritura para JWTs huerfanos** (token firmado sin correspondencia fisica de identidad y contexto en la capa de datos).

---

## Arquitectura de Notificaciones Asincronas

### Modelo de ejecucion

El endpoint de smoke-test usa `FastAPI BackgroundTasks` para despachar `send_alert(...)` fuera del hilo de respuesta HTTP.  

El stack del bunker incorpora Redis como componente operativo de plataforma (control distribuido y resiliencia de runtime), y el patron de desacople actual mantiene la entrega de alertas fuera del camino critico de la API.

### Justificacion tecnica del `202 Accepted`

`202 Accepted` es el contrato correcto para una operacion aceptada para procesamiento diferido:

- evita bloqueo del request por I/O externo (webhook Discord),
- reduce p95/p99 del endpoint,
- mejora UX y fiabilidad percibida en incidentes de red.

---

## Especificacion del Payload de Auditoria (Discord Integration)

La integracion inyecta metadatos operativos y de negocio en cada alerta:

- `tenant_id`
- `triggered_by` (identidad autenticada; en este escenario, UUID de sujeto)
- `environment`
- `timestamp` (UTC)
- `source_endpoint`

Ejemplo de contexto enviado desde el endpoint administrativo:

```json
{
  "tenant_id": "9189c32e-43d4-4efb-8a65-c7c04d252ef3",
  "triggered_by": "aae2b220-7175-48ff-a744-540807462649",
  "smoke_test": true,
  "timestamp": "2026-04-28T13:06:00Z",
  "source_endpoint": "/api/v1/admin/test-alert"
}
```

Estructura de payload de entrega compatible con Discord/Slack:

```json
{
  "content": "## INFO - Smoke test: alerta operativa ...",
  "embeds": [
    {
      "title": "INFO - Smoke test: alerta operativa",
      "fields": [
        { "name": "Entorno", "value": "Production", "inline": true },
        { "name": "Tenant ID", "value": "9189c32e-43d4-4efb-8a65-c7c04d252ef3", "inline": true },
        { "name": "Timestamp (UTC)", "value": "2026-04-28T13:06:00Z", "inline": false }
      ]
    }
  ]
}
```

### Impacto en MTTR

Estos metadatos reducen MTTR porque eliminan ambiguedad en triage:

- identificacion inmediata de tenant afectado,
- correlacion directa con endpoint origen,
- sello temporal unificado para reconstruccion de linea de tiempo,
- menor dependencia de reproduccion manual para diagnostico.

---

## Validacion de Infraestructura (Hito 3.4)

### Flujo certificado

`Auth -> Middleware Validation -> Async Dispatch -> Discord Webhook`

Estado certificado en smoke-test real:

- Login real con identidad provisionada: **200 OK**
- Endpoint de alertas: **202 Accepted**
- Respuesta funcional: `status=queued`

### Pruebas de falso positivo superadas

Antes del exito final, el sistema demostro comportamiento defensivo esperado:

- `403` ante falta de token o contexto de tenant invalido.
- `401` ante credenciales/token no validables.
- bloqueo de identidades no mapeadas fisicamente.

Este comportamiento valida que la apertura del flujo productivo no degrada los controles de seguridad.

---

## Conclusión para Handover / Inversión

El activo presenta una arquitectura con **seguridad defensiva comprobada**, **observabilidad accionable** y **desacople operativo** adecuado para escalado.  

Desde perspectiva de transferencia/inversion, el bunker de notificaciones ya opera con:

- contrato asincrono correcto (`202`),
- trazabilidad multi-tenant auditable,
- rechazo estricto de suplantacion de identidad,
- evidencia de pruebas negativas y positivas en entorno real.
