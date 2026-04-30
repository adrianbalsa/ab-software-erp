# Reglas de alertas P1 v1 (auth, VeriFactu, DB, Redis)

**Versión:** 1.0 · **Vigencia:** desde 2026-04-29 · **Owner:** Adrian (solo-founder)  
**Objetivo DD:** alertas operativas mínimas alineadas con `SLO_MINIMAL_V1.md` y `MONITORING_OBSERVABILITY.md`.

## Principios

1. **Primera señal:** monitores sintéticos sobre `/live` y `/health/deep` (latencia + código HTTP).
2. **Segunda señal:** Sentry (errores y, si está activado, rendimiento) en entorno **production**.
3. **Canal:** el mismo acordado en `ON_CALL_RUNBOOK.md` (Slack / email / PagerDuty). Webhook genérico: `ALERT_WEBHOOK_URL` + smoke `POST /api/v1/admin/test-alert` (owner).

---

## Mapa rápido: qué vigilar

| Área P1 | Señal principal | Acción de alerta (v1) |
|---------|------------------|------------------------|
| **DB / Supabase** | `checks.supabase`, `checks.postgresql`, `checks.finance_service` en `/health/deep` | Monitor HTTP 503 o cuerpo `status != healthy` |
| **Redis / cola** | `checks.redis`, `checks.redis_queue` (`queue_growth_alert`), `checks.sentry` (prod: DSN obligatorio) | Igual + revisión cola ARQ (ver `REDIS_001_HA_BILLING_QUEUE.md`); si `checks.sentry` falla, configurar `SENTRY_DSN` |
| **VeriFactu / AEAT** | `checks.aeat_mtls_certificates` en `/health/deep` | 503 + detalle certificado / homologación |
| **Auth** | Pico de errores en rutas de autenticación o imposibilidad de emitir tokens | Sentry (issues / transacciones) + opcional monitor de endpoint público estable |

---

## 1) Monitores sintéticos (Better Stack, UptimeRobot, Grafana Cloud, …)

Configurar al menos **dos** monitores HTTPS en **producción** (intervalo recomendado ≤ 3 min, timeout 10–15 s):

| ID | URL | Condición de fallo P1 | Notas |
|----|-----|------------------------|--------|
| **M1-Live** | `GET https://api.<dominio>/live` | HTTP ≠ 2xx o timeout | Proceso vivo (SLI-1 en `SLO_MINIMAL_V1.md`). |
| **M2-Deep** | `GET https://api.<dominio>/health/deep` | HTTP ≠ **200** o timeout | Incluye DB, Redis, Supabase REST, cola, mTLS AEAT según `health_checks.run_deep_health`. |

**Escalación:** notificación inmediata al canal on-call; si hay ventana de mantenimiento declarada, silenciar monitores con comentario en el ticket de cambio.

**Opcional (M3):** segundo probe desde otra región del proveedor para reducir falsos positivos de red.

---

## 2) Interpretación de `/health/deep` (prioridad P1 por `checks`)

Cuando **M2-Deep** falle, clasificar según el JSON (campo `checks`):

| Clave `checks.*` | Significado operativo |
|------------------|-------------------------|
| `supabase` | PostgREST / credenciales service role / red hacia Supabase. |
| `postgresql` | `DATABASE_URL` / motor Postgres (consulta mínima). |
| `finance_service` | Capa de negocio + DB tenant (síntoma frecuente de RLS o conectividad). |
| `redis` | `REDIS_URL` no responde PING. |
| `redis_queue` | Profundidad de cola o `queue_growth_alert=true` (crecimiento sostenido). |
| `aeat_mtls_certificates` | Certificado mTLS AEAT próximo a caducar o ilegible (VeriFactu bloqueado). |
| `sentry` | En **solo** `ENVIRONMENT=production`: `SENTRY_DSN` debe estar configurado (observabilidad P1). Otros entornos: `skipped`. |

Referencia de implementación: `backend/app/core/health_checks.py` → `run_deep_health`.

---

## 3) Sentry (producción)

Crear **Issue alerts** (o equivalente) con destino al canal on-call. Umbrales orientativos para **solo-founder** (ajustar tras 2 semanas de baseline):

| ID | Condición | Ventana | Umbral sugerido |
|----|-----------|----------|-----------------|
| **S1-Error-rate** | Nivel `error` o `fatal` | 5 min | ≥ **10** eventos nuevos **o** umbral relativo si Sentry lo permite (p. ej. +300 % vs baseline). |
| **S2-Auth** | Issues cuyo **transaction** o **URL** contenga `/api/v1/auth` o `/auth` | 10 min | ≥ **5** eventos (posible ataque, rotación JWT rota o Supabase Auth degradado). |
| **S3-VeriFactu** | Mensaje o tag conteniendo `AEAT`, `VeriFactu`, `verifactu`, `mTLS`, `XADES` | 10 min | ≥ **3** eventos (revisar cola `verifactu_envios` y certificados). |
| **S4-P1-critical** | Tag **`p1_critical_route`** presente (Performance / Discover) | 15 min | Opcional: alertar si **p95** de ese tag > **2 s** (mismas rutas que `CriticalPathSentryTagsMiddleware`). |

**Rendimiento (opcional):** *Metric alert* si el **p95** de transacciones clave supera **2 s** durante 15 min (relajar o endurecer según `SLO_MINIMAL_V1.md`). Alternativa: regla **S4-P1-critical** filtrando por el tag anterior.

Privacidad: `backend/app/core/sentry_privacy.py` — no añadir PII en tags o breadcrumbs.

---

## 4) Alertas desde la API (ya cableadas)

- **`GET /health`** (raíz): si Supabase o Redis críticos fallan, se dispara alerta crítica vía servicio de alertas (ver `main.py` bloque health). Útil como red de seguridad si el monitor externo solo apunta a `/health/deep`.
- **`POST /api/v1/admin/test-alert`** (rol **owner**): smoke del webhook operativo tras despliegue (`ON_CALL_RUNBOOK.md` § primeros 15 min).

---

## 5) Registro de evidencia DD (capturas / enlaces)

**No subir secretos ni URLs con tokens.** Guardar en el almacén acordado (Drive, Notion, carpeta interna) y enlazar aquí o en el ticket semanal.

| Evidencia | Qué debe mostrar | Estado |
|-----------|------------------|--------|
| Captura **M1-Live** | URL del monitor, intervalo, últimas 24 h OK | Pendiente |
| Captura **M2-Deep** | URL del monitor, intervalo, últimas 24 h OK | Pendiente |
| Captura **S1–S3** (Sentry) | Lista de alertas con destino Slack/email | Pendiente |
| Opcional | Resultado `POST …/admin/test-alert` + mensaje en canal | Pendiente |

---

## Referencias

- `docs/operations/runbook_v1.md` — incidentes P1: detección, contención, comunicación, RCA.
- `docs/operations/SLO_MINIMAL_V1.md`
- `docs/operations/MONITORING_OBSERVABILITY.md`
- `docs/operations/ON_CALL_RUNBOOK.md`
- `docs/operations/REDIS_001_HA_BILLING_QUEUE.md`
- `docs/operations/AEAT_VERIFACTU_HOMOLOGACION.md`
