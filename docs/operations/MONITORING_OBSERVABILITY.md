# OBS-003: monitoreo, `/health/deep` y alertas (Fase 3.3)

## Objetivo

Garantizar **detección temprana** de fallos en API y dependencias (DB, Redis, cola, VeriFactu mTLS) y **notificación** al canal on-call (objetivo operativo: **menos de 5 minutos** entre fallo visible y alerta, según intervalo del monitor y reglas Sentry).

## 1. `GET /health/deep` (ya expuesto en la API)

- **Ruta:** `GET /health/deep` (sin autenticación; exenta de rate limit global).
- **Cuerpo JSON:** `status` ∈ `healthy` | `degraded` y `checks` con entradas (`supabase`, `postgresql`, `redis`, `redis_queue`, `geocoding_cache`, `pgbouncer`, `aeat_mtls_certificates`, …).
- **HTTP:** `200` si `status=healthy`, **`503`** si `degraded` (dependencia crítica en mal estado).
- **Implementación:** `backend/app/api/v1/health.py` + `backend/app/core/health_checks.py`.

### Sonda CLI (CI o laptop)

```bash
python backend/scripts/check_golive_readiness.py --base-url https://api.<dominio> --strict
python backend/scripts/check_golive_readiness.py --base-url https://api.<dominio> --summarize-deep
```

`--strict` exige **200** también en `/health/deep` (sin degradación).  
`--summarize-deep` imprime resumen de `checks.*` tras la petición (útil para logs/archivo de evidencia).

## 2. Monitor externo (Better Stack, UptimeRobot, Grafana Cloud, etc.)

1. Crear monitor **HTTPS** contra `https://api.<dominio>/health/deep`.
2. Considerar **intervalo ≤ 3 minutos** (o el mínimo que permita el plan) para acercarse al criterio de 5 minutos; combinar con alertas Sentry si el fallo no altera HTTP (p. ej. errores de negocio).
3. Alertas a **Slack / email / PagerDuty** según canal acordado en `ON_CALL_RUNBOOK.md`.
4. Opcional: segundo monitor sobre `GET /live` (superficie mínima) para distinguir “proceso caído” vs “dependencias degradadas”.

**Better Stack:** crear *Heartbeat* o *Monitor* con URL anterior, umbrales de latencia y escalación. Documentar URL del monitor en `OPS_001` (sin secretos).

## 3. Sentry (APM y errores)

| Superficie | Variable | Notas |
|------------|----------|--------|
| API | `SENTRY_DSN` | Inicialización en `app.main` tras `get_settings()`. |
| Frontend | `NEXT_PUBLIC_SENTRY_DSN` | Next.js + `instrumentation.ts`. |
| Release | `APP_RELEASE` / SHA plataforma | Correlación deploy ↔ errores. |

**Alertas:** en el proyecto Sentry, configurar *Issue Alerts* y, si aplica, *Metric Alerts* (tasa de errores, apdex) con destino **Slack** o email del equipo. Botón de prueba en UI Sentry o flujo de error controlado (ver §5).

Privacidad: `backend/app/core/sentry_privacy.py` y política de no enviar PII en breadcrumbs.

## 4. Alertas desde código (`ALERT_WEBHOOK_URL`)

Errores críticos puntuales pueden notificarse vía `docs/operations` / `app/core/alerts.py` (Discord/Telegram genérico). No sustituye Sentry ni el monitor HTTP; sirve como canal adicional para scripts o fallos fuera de request.

## 5. Simulacro controlado (evidencia Fase 3.3)

1. **HTTP:** bajar temporalmente una dependencia en **staging** (o bloquear Redis de prueba) y comprobar que el monitor marca **fallo** y llega notificación (captura con hora UTC).
2. **Sentry:** usar el flujo de prueba documentado en frontend (p. ej. botón de test en login de desarrollo) **solo en entorno no productivo**, o *Send test alert* desde Sentry → Slack.
3. Registrar en ticket: hora inicio/fin, canal, latencia aproximada hasta la alerta.

## 6. Evidencia (no en git público)

| Artefacto | Descripción |
|-------------|----------------|
| Export o captura de reglas de monitor (URL, intervalo, umbrales) | |
| Captura de alerta recibida en Slack/email | |
| Salida de `check_golive_readiness.py --base-url … --strict --summarize-deep` con fecha | |

## 7. Hito 1 GO-live (monitorización P1 en código)

| Objetivo | Implementación |
|----------|------------------|
| **Sentry en producción** | `GET /health/deep` incluye `checks.sentry`: en `ENVIRONMENT=production` exige `SENTRY_DSN` no vacío (sin exponer el valor). Si falta, `status=degraded` y HTTP **503**. |
| **Latencia / triage en rutas críticas** | Middleware `CriticalPathSentryTagsMiddleware` añade tag **`p1_critical_route`** en Sentry Performance: `verifactu_submit_final`, `advisor_ask`, `health_readiness`, `bi_financial_health`. En Discover / Performance filtrar por ese tag. |
| **Redis caído (arranque)** | Antes de cada `RuntimeError` por Redis en `warmup_rate_limit_backend` y en fallos de configuración de `get_rate_limit_strategy` / `get_rate_limit_storage_uri`, se emite **mensaje Sentry nivel fatal** (`notify_redis_shared_rate_limit_fatal`). |
| **Redis intermitente (runtime)** | Si `strategy.hit` falla en middlewares de rate limit (fail-open), **Sentry error** acotado a 1 evento / 5 min por canal (`notify_redis_rate_limit_runtime_degraded`). |
| **Cadena VeriFactu rota** | Tras el webhook existente: `GET /verificar-cadena` con discrepancias y `GET /audit/verify-chain` con `is_valid=false` disparan **Sentry error** (`notify_verifactu_chain_integrity_failure`). |

**Cierre operativo sugerido (evidencia):** (1) monitor M2 con `checks.sentry` OK en prod; (2) en Sentry, filtrar transacciones con `p1_critical_route` y comprobar latencias; (3) tres alertas de prueba: *Send test alert* en Sentry, `POST /api/v1/admin/test-alert` (owner), y simulacro Redis en staging documentado en `ALERT_RULES_P1_V1.md` §5.

## Referencias

- `docs/operations/ALERT_RULES_P1_V1.md` — reglas de alertas P1 (auth, VeriFactu, DB, Redis) + plantilla de evidencia.
- `docs/operations/SLO_MINIMAL_V1.md` — SLI/SLO mínimos v1 (DD Fase 1.3): disponibilidad, error rate, p95.
- `docs/operations/ON_CALL_RUNBOOK.md` — guardia y severidades.
- `docs/operations/health_recovery.md` — interpretación de estados.
- `docs/operations/REDIS_001_HA_BILLING_QUEUE.md` — métricas en `/health/deep`.
- `docs/operations/MTLS_CERTIFICATE_RENEWAL.md` — `checks.aeat_mtls_certificates`.
