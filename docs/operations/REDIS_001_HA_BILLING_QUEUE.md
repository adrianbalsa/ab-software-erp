# REDIS-001: Redis HA para cola de facturacion

## Objetivo

Evitar perdida, bloqueo o falta de visibilidad en trabajos criticos de facturacion y VeriFactu. La cola usa ARQ + Redis y se considera dependencia critica para:

- Envio diferido a AEAT desde facturas finalizadas.
- Reintentos operativos de facturas con `aeat_sif_estado=pendiente_envio`.
- Rate limiting distribuido y proteccion de endpoints costosos.

## Estrategia HA

| Entorno | Estrategia recomendada | Requisito |
|---------|------------------------|-----------|
| Railway / managed Redis | Redis administrado con persistencia/replica/failover del proveedor | `REDIS_URL` con auth/TLS (`rediss://` si el proveedor lo expone). |
| VPS self-hosted | Redis Sentinel con 3 sentinels y al menos 1 replica | `REDIS_SENTINEL_HOSTS` + `REDIS_SENTINEL_MASTER`. |
| Desarrollo local | Redis simple en Docker Compose | Sin HA; no valido para produccion. |

Regla operativa: produccion no debe usar Redis sin autenticacion ni endpoint publico sin TLS/red privada. Si el proveedor entrega un endpoint `rediss://`, usarlo en `REDIS_URL`.

## Configuracion de runtime

Variables compartidas por API y worker:

| Variable | Obligatoria | Descripcion |
|----------|-------------|-------------|
| `REDIS_URL` | Si | DSN Redis con password/db/TLS. En Sentinel se usa para auth, db y modo TLS. |
| `ARQ_BILLING_QUEUE_NAME` | No | Cola ARQ de facturacion. Por defecto `arq:queue`. API y worker deben coincidir. |
| `REDIS_SENTINEL_HOSTS` | No | Lista `host:port` separada por comas para Sentinel. |
| `REDIS_SENTINEL_MASTER` | No | Nombre del master Sentinel. Por defecto `mymaster`. |
| `REDIS_CONN_TIMEOUT_SECONDS` | No | Timeout de conexion ARQ. Por defecto `2`. |
| `REDIS_CONN_RETRIES` | No | Reintentos de conexion ARQ. Por defecto `5`. |
| `REDIS_CONN_RETRY_DELAY_SECONDS` | No | Espera entre reintentos de conexion. Por defecto `1`. |
| `REDIS_MAX_CONNECTIONS` | No | Limite de conexiones por proceso. Recomendado `50` como punto inicial. |
| `REDIS_QUEUE_GROWTH_ALERT_MINUTES` | No | Ventana para alertar si `queue_depth` crece en muestras sucesivas. Por defecto `15`. |
| `REDIS_QUEUE_GROWTH_MIN_DEPTH` | No | Profundidad minima para activar alerta de crecimiento sostenido. Por defecto `10`. |

Archivos relevantes:

- `backend/app/core/redis_config.py`: configuracion compartida Redis/ARQ, Sentinel y cola.
- `backend/app/core/arq_queue.py`: encolado API hacia `ARQ_BILLING_QUEUE_NAME`.
- `backend/app/worker.py`: worker ARQ con retry/backoff y healthcheck.
- `backend/app/core/health_checks.py`: metricas Redis/cola en `/health/deep`.
- `public.verifactu_dead_jobs`: dead-letter durable de jobs AEAT agotados; no sustituye a `verifactu_envios`.

## Retry y backoff del worker

El job `submit_to_aeat` aplica dos capas:

1. Cliente AEAT: `AEAT_HTTP_MAX_ATTEMPTS=6` con backoff exponencial para HTTP `429/5xx` y transporte.
2. Cola ARQ: maximo `6` intentos por job con backoff `10s`, `20s`, `40s`, `80s`, `160s`, `300s`.

Se reintenta a nivel cola cuando:

- Redis falla durante el bucket de egress (`RedisError`).
- Hay errores transitorios de red/timeout.
- El sender deja la factura en `pendiente_envio` con `AEAT_TIMEOUT`, `AEAT_CONNECTION` o `REINTENTO_AGOTADO`.

No se reintentan ciegamente errores no recuperables como XML invalido, SOAP mal formado, certificado ausente/ilegible o fallo de firma (`XSD_REQUEST`, `SOAP_MALFORMED`, `CERT`, `CERT_READ`, `XADES`).

## Observabilidad

Cada intento registra auditoria con:

- `action_result`: `success`, `retry`, `retry_exhausted` o `error`.
- `job_try` y `max_tries`.
- `factura_id`, `empresa_id` y resultado del worker cuando existe.

Cuando `submit_to_aeat` agota todos los reintentos de ARQ (`retry_exhausted`), el worker crea una fila `open` en `verifactu_dead_jobs` si no existe ya otra abierta para la misma factura/job. Esta tabla sirve para bandeja operativa y evidencia durable; no se debe consumir como cola paralela ni borrar para "arreglar" el incidente.

`/health/deep` expone:

- `checks.redis`: ping basico.
- `checks.redis_queue.queue_name`: nombre de cola ARQ.
- `checks.redis_queue.queue_depth`: profundidad de cola.
- `checks.redis_queue.connected_clients`.
- `checks.redis_queue.blocked_clients`.
- `checks.redis_queue.used_memory`.
- `checks.redis_queue.rejected_connections`.
- `checks.redis_queue.queue_growth_alert`: `true` si `queue_depth` crece de forma sostenida durante `REDIS_QUEUE_GROWTH_ALERT_MINUTES`.
- `checks.redis_queue.queue_growth_duration_seconds`: segundos acumulados desde que empezo el crecimiento sostenido.

Umbrales iniciales obligatorios:

| Senal | Umbral inicial | Accion |
|-------|----------------|--------|
| Redis caido | `checks.redis.ok=false` | Restaurar Redis/failover y reiniciar worker si no reconecta. |
| Cola creciendo | `queue_growth_alert=true` (`queue_depth >= 10` y creciendo durante 15 min) | Revisar worker, AEAT y Redis antes de purgar o reencolar. |
| Cola bloqueada | `queue_depth > 25` sostenido 15 min sin jobs completados | Revisar logs worker, AEAT y Redis. |
| Cola critica | `queue_depth > 100` o crecimiento durante 30 min | P1 fiscal si afecta emision; escalar a owner API/worker/Redis. |
| Clientes bloqueados | `blocked_clients > 0` sostenido | Revisar comandos bloqueantes o saturacion. |
| Conexiones rechazadas | `rejected_connections > 0` | Subir limite/provisionamiento y revisar pooling. |
| Memoria | `used_memory > 80% maxmemory` | Ampliar plan o ajustar retencion/eviction. |

Valores productivos recomendados de arranque:

```env
REDIS_QUEUE_GROWTH_ALERT_MINUTES=15
REDIS_QUEUE_GROWTH_MIN_DEPTH=10
```

## Checks operativos recurrentes

### Diario

- Revisar `GET /health/deep` y confirmar `checks.redis.ok=true` y `checks.redis_queue.ok=true`.
- Confirmar que `queue_depth` no crece de forma sostenida durante mas de 15 minutos.
- Revisar logs del worker buscando `submit_to_aeat`, `retry_exhausted`, `redis_error` o `MaxRetries`.
- Comprobar que no hay facturas en `pendiente_envio` fuera de la ventana operativa esperada.

### Semanal

- Verificar en Railway/proveedor Redis que persistencia, replica/failover y alertas siguen activos.
- Revisar tendencia de `used_memory`, `connected_clients`, `blocked_clients` y `rejected_connections`.
- Validar que API y worker siguen compartiendo `REDIS_URL` y `ARQ_BILLING_QUEUE_NAME` tras despliegues.
- Ejecutar una prueba controlada de encolado en staging y confirmar auditoria `VERIFACTU_JOB_COMPLETED`.
- Confirmar que la alerta `queue_growth_alert=true` esta cableada en el sistema de monitorizacion para abrir aviso si se mantiene mas de una ventana.

### Mensual

- Revisar capacidad del plan Redis contra picos de facturacion y campañas de cierre fiscal.
- Ejecutar simulacro documentado de restart/failover en staging.
- Archivar evidencia: captura de healthcheck, logs del worker, resultado del smoke y acciones correctivas.

## Triage de guardia

1. Clasificar impacto: API caida, worker parado, cola acumulada o solo degradacion de metricas.
2. Mirar `checks.redis.detail` y `checks.redis_queue.detail`; si Redis no responde, tratar como P2 salvo que bloquee emision fiscal critica, donde pasa a P1.
3. Si `queue_depth > 0` pero Redis responde, revisar logs del worker antes de reiniciar servicios.
4. Si el worker fallo por AEAT/transporte, no purgar cola; validar que los jobs quedan reintentables.
5. Tras recuperar Redis/worker, ejecutar `retry-pending` solo con usuario autorizado y registrar facturas afectadas.

## Procedimiento de verificacion

1. Confirmar que API y worker tienen el mismo `REDIS_URL` y `ARQ_BILLING_QUEUE_NAME`.
2. En Railway/VPS, validar que el worker arranca y publica healthcheck ARQ cada 60s.
3. Ejecutar `GET /health/deep` y verificar `checks.redis.ok=true` y `checks.redis_queue.ok=true`.
4. Encolar una factura de prueba o usar `POST /api/v1/verifactu/retry-pending` en entorno de homologacion.
5. Confirmar logs del worker con `submit_to_aeat` y auditoria `VERIFACTU_JOB_COMPLETED`.
6. Simular fallo transitorio controlado en staging y verificar que aparece `action_result=retry` antes de agotarse.

## Prueba de recuperacion staging

Objetivo: demostrar que un fallo transitorio de Redis/worker no pierde trabajos VeriFactu y que la alerta de crecimiento sostenido aparece antes de impacto fiscal prolongado.

Precondiciones:

- Staging usa Redis HA administrado o Sentinel, con `REDIS_QUEUE_GROWTH_ALERT_MINUTES=5` y `REDIS_QUEUE_GROWTH_MIN_DEPTH=3` para acortar el simulacro.
- API y worker apuntan al mismo `ARQ_BILLING_QUEUE_NAME`.
- Hay al menos 3 facturas de prueba en `pendiente_envio` o un tenant de homologacion capaz de generar facturas dummy.

Pasos:

1. Ejecutar `GET /health/deep` y guardar evidencia de `checks.redis.ok=true`, `checks.redis_queue.ok=true` y `queue_depth` inicial.
2. Detener solo el worker de staging durante 6 minutos; no detener API ni Redis.
3. Encolar al menos 3 envios con `POST /api/v1/verifactu/retry-pending` o finalizando facturas dummy.
4. Repetir `GET /health/deep` cada minuto hasta observar `checks.redis_queue.queue_growth_alert=true` y `status=degraded`.
5. Arrancar el worker y esperar a que procese la cola.
6. Confirmar `queue_depth=0` o vuelve al baseline, `checks.redis_queue.ok=true`, logs `submit_to_aeat` y auditoria `VERIFACTU_JOB_COMPLETED`.
7. Guardar evidencia: timestamps, profundidad maxima, duracion de alerta, jobs procesados y cualquier `retry_exhausted`.

Criterio de aceptacion: no hay trabajos perdidos, la cola se drena tras recuperar worker/Redis, y la alerta se dispara dentro de la ventana configurada.

## Runbook de fallo

1. Revisar `/health/deep` y logs del worker.
2. Si Redis esta caido, ejecutar failover en proveedor o recuperar Sentinel.
3. Si Redis vuelve pero la API no encola, reiniciar API para recrear el pool ARQ.
4. Si el worker no consume, reiniciar worker y comprobar `ARQ_BILLING_QUEUE_NAME`.
5. Si hay facturas pendientes tras la recuperacion, ejecutar `POST /api/v1/verifactu/retry-pending` con usuario autorizado.
6. Revisar `verifactu_dead_jobs` con `status='open'`; resolver o ignorar solo tras confirmar el estado real en AEAT y `facturas.aeat_sif_*`.
7. Registrar incidente con ventana de impacto, facturas afectadas y evidencia de reintento/auditoria.

## Checklist REDIS-001

- [ ] Redis productivo usa servicio HA administrado o Sentinel documentado.
- [ ] `REDIS_URL` incluye auth y TLS/red privada segun proveedor.
- [ ] API y worker comparten `ARQ_BILLING_QUEUE_NAME`.
- [ ] `REDIS_CONN_TIMEOUT_SECONDS`, `REDIS_CONN_RETRIES` y `REDIS_MAX_CONNECTIONS` estan definidos en produccion.
- [ ] Worker `submit_to_aeat` aplica retry/backoff a nivel cola.
- [ ] `/health/deep` muestra metricas Redis y profundidad de cola.
- [ ] `/health/deep` alerta `queue_growth_alert=true` cuando la cola crece de forma sostenida.
- [ ] Auditoria registra intentos, reintentos y agotamiento.
- [ ] `verifactu_dead_jobs` registra jobs agotados de forma idempotente.
- [ ] Existe procedimiento para reencolar `pendiente_envio`.
- [ ] Alertas activas para caida Redis, cola bloqueada, memoria, clientes bloqueados y conexiones rechazadas.
- [ ] Umbrales de cola (`>=10/15min`, `>25/15min`, `>100/30min`) estan configurados en monitorizacion.
- [ ] Runbook de guardia enlazado y owners de API/worker/Redis identificados.
- [ ] Simulacro de failover/restart probado en staging durante el ultimo trimestre.
