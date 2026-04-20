# 🚨 30-Second Incident Recovery

```bash
docker compose ps
docker compose logs --tail 20
docker compose restart backend redis
curl -fsS http://127.0.0.1:8000/live
curl -fsS http://127.0.0.1:8000/health
```

# Health Recovery Runbook (5 min)

Guía breve para restaurar `AB Logistics OS` cuando fallan comprobaciones de salud. Marco DRP de alto nivel: `docs/operations/DISASTER_RECOVERY.md`.

## Scope

- Stack: Docker Compose (`docker-compose.yml` / `docker-compose.prod.yml`)
- **Liveness** (proceso vivo, sin TrustedHost): `GET /live` → `{"status":"ok","request_id":"..."}` y cabecera `X-Request-ID`
- **Readiness** (dependencias críticas): `GET /health` → Supabase REST + Redis **obligatorio**
- **Readiness profundo**: `GET /health/deep` → capa de negocio, Postgres opcional, Redis, PgBouncer TCP opcional
- Objetivo: recuperar servicio en pocos minutos

## Endpoint Specs

### `GET /live`

- Uso: balanceadores (Railway `healthcheckPath`, Docker si se prefiere liveness barato).
- No comprueba Supabase ni Redis.

### `GET /health`

Respuesta esperada:

```json
{
  "status": "healthy|unhealthy",
  "request_id": "uuid-opaque",
  "checks": {
    "supabase": {
      "ok": true,
      "detail": "supabase_ok|supabase_http_5xx|supabase_error:...",
      "skipped": false
    },
    "redis": {
      "ok": true,
      "detail": "redis_ping_ok|redis_error:...",
      "skipped": false
    }
  }
}
```

**Nota:** Redis no configurado se marca como **fallo** en este endpoint (readiness estricto para orquestación que exija colas/rate-limit compartidos).

Fast check:

```bash
curl -fsS http://127.0.0.1:8000/live
curl -fsS http://127.0.0.1:8000/health
```

Container-native:

```bash
docker compose exec backend curl -fsS http://127.0.0.1:8000/live
docker compose exec backend curl -fsS http://127.0.0.1:8000/health
```

## Alert Levels

### P1 - Supabase Down (Critical)

- Signal: `checks.supabase.ok=false` en `/health` o fallo equivalente en `/health/deep`
- Impact: datos/auth no disponibles
- Action: incidente mayor; ver `DISASTER_RECOVERY.md` §4.2

### P2 - Redis Down (High)

- Signal: `checks.redis.ok=false`
- Impact: colas, rate limit distribuido; API puede degradar
- Action: restaurar Redis; ver §2–3 abajo

## 5-Minute Recovery Procedures

## 1) Confirm failing dependency

```bash
docker compose ps
docker compose logs --since=10m backend
docker compose exec backend curl -sS http://127.0.0.1:8000/live
docker compose exec backend curl -sS http://127.0.0.1:8000/health
```

For production file:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --since=10m backend
docker compose -f docker-compose.prod.yml exec backend curl -sS http://127.0.0.1:8000/live
docker compose -f docker-compose.prod.yml exec backend curl -sS http://127.0.0.1:8000/health
```

## 2) Redis recovery path

```bash
docker compose restart redis
docker compose ps redis
docker compose logs --since=5m redis
docker compose exec redis redis-cli ping
docker compose exec backend curl -sS http://127.0.0.1:8000/health
```

If still failing, restart backend after Redis is healthy:

```bash
docker compose restart backend
docker compose exec backend curl -sS http://127.0.0.1:8000/health
```

## 3) Supabase recovery path

Supabase is external. Validate credentials/network first, then restart backend.

```bash
docker compose exec backend env | rg "SUPABASE_URL|SUPABASE_SERVICE_KEY|SUPABASE_ANON_KEY"
docker compose restart backend
docker compose logs --since=10m backend
docker compose exec backend curl -sS http://127.0.0.1:8000/health
```

If keys/URL are wrong:

1. Fix `.env`
2. Recreate backend with updated env

```bash
docker compose up -d --force-recreate backend
docker compose exec backend curl -sS http://127.0.0.1:8000/health
```

## 4) Full stack recovery (last resort)

```bash
docker compose up -d redis backend frontend nginx
docker compose ps
docker compose exec backend curl -sS http://127.0.0.1:8000/live
docker compose exec backend curl -sS http://127.0.0.1:8000/health
```

Production variant:

```bash
docker compose -f docker-compose.prod.yml up -d redis backend frontend caddy
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml exec backend curl -sS http://127.0.0.1:8000/live
docker compose -f docker-compose.prod.yml exec backend curl -sS http://127.0.0.1:8000/health
```

## Verification Checklist (Post-Restart)

- `docker compose ps` shows `healthy` for `redis`, `backend`, and `frontend`
- `GET /live` returns `200` and `status=ok`
- `GET /health` returns:
  - `"status":"healthy"`
  - `checks.supabase.ok=true`
  - `checks.redis.ok=true`
- Frontend responds `200/3xx` from local service URL
- No fresh auth/database connection errors in backend logs (last 3-5 minutes)

## Troubleshooting and Logs

Docker logs are now rotated (`json-file`, `max-size=10m`, `max-file=3` per service).

Use recent-window queries to avoid missing rotated segments:

```bash
docker compose logs --since=15m backend
docker compose logs --since=15m redis
docker compose logs --since=15m frontend
```

Targeted patterns:

```bash
docker compose logs --since=15m backend | rg -i "timeout|timed out|connection refused|dns|auth|invalid|credential|supabase|redis"
docker compose logs --since=15m redis   | rg -i "error|fail|oom|loading|ready"
```

Common failure hints:

- `supabase_http_5xx` -> Supabase service incident or upstream outage
- `supabase_error:*` -> DNS/network/TLS/credential issue from backend
- `redis_error:*` -> Redis container unavailable, wrong `REDIS_URL`, or startup delay

## Escalation Trigger

Escalate immediately if:

- Supabase remains down more than 5 minutes after credential/network validation
- Redis fails to become healthy after restart + backend recycle
- `/health` stays `unhealthy` while containers are `up` (possible external dependency outage)
