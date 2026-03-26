# Fase 4 — Producción, observabilidad y CI

## Variables de entorno

| Variable | Uso |
|----------|-----|
| `ENVIRONMENT` | `development` (defecto) o `production` |
| `OFFICIAL_FRONTEND_ORIGIN` | En **producción**, origen HTTPS del front (ej. `https://app.tudominio.com`) |
| `CORS_ALLOW_ORIGINS` | Lista separada por comas de orígenes adicionales |
| `CORS_ALLOW_ORIGIN_REGEX` | En prod, solo si se define (no vacío); en dev, por defecto previews Vercel |
| `SENTRY_DSN` | Backend (FastAPI) y opcionalmente servidor Next si se reutiliza |
| `NEXT_PUBLIC_SENTRY_DSN` | **Obligatorio** para Sentry en el navegador (Next 16) |
| `SENTRY_TRACES_SAMPLE_RATE` / `NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE` | Muestreo de trazas (0–1) |

## Health

- `GET /health` — Supabase REST + `FinanceService.financial_summary` (tenant sintético). `503` si algo falla.
- `GET /ready` — Solo proceso vivo (Kubernetes).

## Logs JSON

Cada petición escribe una línea JSON en stdout (`message: http_access`) con `duration_ms`, `path`, `empresa_id` (JWT app con claim `empresa_id`), `auth_subject`.

## Docker

Desde la raíz del monorepo:

```bash
docker build -t ab-logistics-api .
docker run -p 8000:8000 -e SUPABASE_URL=... -e SUPABASE_KEY=... ... ab-logistics-api
```

Railway: `Dockerfile` en raíz, `PORT` inyectado por la plataforma.

## GitHub Actions

`.github/workflows/deploy.yml` ejecuta `pytest tests/ -v` en `backend/` en cada push/PR a `main` o `master` (bloquea despliegue si fallan los tests, incluido el Math Engine).
