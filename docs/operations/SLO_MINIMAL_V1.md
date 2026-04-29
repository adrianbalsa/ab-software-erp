# SLO mínimos v1 (Fase 1.3 — observabilidad auditable)

**Versión:** 1.0 · **Vigencia:** desde 2026-04-29 · **Owner:** Adrian (solo-founder)  
**Objetivo DD:** definir SLI/SLO mínimos medibles (disponibilidad, tasa de error, latencia p95) sin depender de un stack APM completo.

## Alcance

| Superficie | Entorno | Notas |
|------------|---------|--------|
| API FastAPI (Railway) | Staging + Producción | Host canónico `https://api.<dominio>` |
| Frontend (Vercel) | Producción | Fuera de este v1 salvo error rate agregado en Sentry si aplica |

No sustituye `docs/operations/MONITORING_OBSERVABILITY.md` ni `ON_CALL_RUNBOOK.md`; los **complementa** con números y ventanas de medición.

---

## Definiciones

### SLI-1 — Disponibilidad sintética (proceso vivo)

- **Qué se mide:** `GET /live` responde **HTTP 2xx** en menos de **3 s** (timeout del probe).
- **Ventana SLO:** **30 días** calendario, rolling (cada día se recalcula sobre los últimos 30 días de checks del monitor externo).
- **SLO:** **≥ 99,5 %** de checks OK en **producción**.

**Fuente de verdad:** monitor HTTPS externo (Better Stack, UptimeRobot, Grafana Cloud, etc.) documentado en `MONITORING_OBSERVABILITY.md` §2.

### SLI-2 — Salud profunda (dependencias)

- **Qué se mide:** `GET /health/deep` responde **HTTP 200** y cuerpo con `status: "healthy"` (sin degradación; ver `backend/app/api/v1/health.py`).
- **Ventana SLO:** **30 días** rolling.
- **SLO:** **≥ 99,0 %** de checks OK en **producción**.

**Rationale:** un `503` con `degraded` puede ser correcto ante caída puntual de Redis/DB; el SLO es más exigente que “solo proceso arriba” pero más realista que exigir 99,9 % sobre todas las dependencias.

### SLI-3 — Tasa de error HTTP (API)

- **Qué se mide:** fracción de respuestas **HTTP 5xx** sobre el total de peticiones HTTP atendidas por la API en el período (incluye timeouts tratados como fallo si el balanceador las cuenta como 5xx).
- **Ventana SLO:** **7 días** rolling.
- **SLO:** **< 0,5 %** (0,005) de 5xx en **producción**.

**Fuente de verdad (prioridad):**

1. Métricas del proveedor de hosting (Railway) si exportan contadores por status, **o**
2. Sentry *metric alerts* / vistas de tasa de fallo por entorno `production`, **o**
3. Logs estructurados agregados (último recurso; documentar consulta).

**Exclusiones explícitas (v1):** `429` por rate limit no cuenta como fallo de SLO de error rate (es comportamiento esperado bajo abuso o burst); si se desea incluir en v2, anótalo en revisión mensual.

### SLI-4 — Latencia p95 (API)

- **Qué se mide:** percentil **95** del tiempo de respuesta **server-side** de la API para tráfico representativo.

**Rutas de referencia (mínimo v1):**

| Ruta | Método | Autenticación | Notas |
|------|--------|---------------|--------|
| `/health` | GET | No | Baseline barato |
| `/api/v1/health` o equivalente documentado en deploy | GET | No | Si existe en el despliegue |

- **Ventana SLO:** **7 días** rolling.
- **SLO:** **p95 ≤ 1,5 s** en producción para las rutas anteriores (probes sintéticos o transacciones Sentry con *Performance*).

**Fuente de verdad:** Sentry Performance (transacciones) y/o latencia reportada por el monitor sintético sobre `/health`.

---

## Cumplimiento y revisión

| Frecuencia | Acción |
|------------|--------|
| Semanal (viernes) | Revisar dashboard del monitor + Sentry; anotar brecha vs SLO en el ticket semanal o nota de ops. |
| Mensual | Revisar si los umbrales siguen siendo realistas; ajustar v1.1 si el volumen o la arquitectura cambian. |

**Incumplimiento:** abrir incidente según `ON_CALL_RUNBOOK.md`; si la brecha es solo en SLI-2 (deep) pero SLI-1 cumple, clasificar como degradación de dependencia (P2/P3) salvo que afecte a VeriFactu o cobros (entonces P1 según matriz del runbook).

---

## Evidencia DD (artefactos)

| Artefacto | Descripción |
|-----------|-------------|
| Este documento | Definición acordada de SLI/SLO v1 |
| Captura o URL del monitor | Intervalo, URL (`/live`, `/health/deep`), región del probe |
| Sentry | Vista o alerta de error rate / performance (producción) |
| Opcional | Salida de `python backend/scripts/check_golive_readiness.py --base-url … --strict --summarize-deep` archivada con fecha UTC |

---

## Referencias

- `docs/operations/ALERT_RULES_P1_V1.md` — umbrales y reglas de alerta P1 alineadas con estos SLI.
- `docs/operations/MONITORING_OBSERVABILITY.md` — `/health/deep`, monitores, Sentry, webhook.
- `docs/operations/ON_CALL_RUNBOOK.md` — severidad y primeros 15 minutos.
- `backend/scripts/check_golive_readiness.py` — comprobación CLI estricta.
