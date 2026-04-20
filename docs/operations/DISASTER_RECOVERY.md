# Plan de recuperación ante desastres (DRP) — AB Logistics OS

Documento operativo para **fase 6 (robustez y resiliencia)**: objetivos de recuperación, señales de alarma y rutas de escalado. Complementa `health_recovery.md` (recuperación en minutos) con el marco **RPO/RTO** y dependencias externas.

## 1. Alcance y supuestos

| Componente | Rol en continuidad |
|------------|-------------------|
| **Supabase** (Postgres + Auth + PostgREST) | Fuente de verdad de datos y RLS; caída prolongada = parada de negocio. |
| **Postgres dedicado** (`DATABASE_URL` en producción) | Transacciones VeriFactu y candados; debe mantenerse coherente con la estrategia de backup. |
| **Redis** | Rate limiting, colas ARQ, cachés; caída = degradación fuerte (sin colas / límites compartidos). |
| **API FastAPI** (Railway / VPS / Docker) | Punto de entrada HTTP; escala horizontal según plataforma. |
| **Frontend Next.js** (Vercel u otro) | SPA; errores aislados no bloquean la API. |
| **Secretos** (`SecretManagerService`, Vault/AWS) | Rotación y runbook en `README_SECURITY.md`. |

## 2. Objetivos de recuperación (orientativos)

| Métrica | Objetivo de diseño | Notas |
|---------|-------------------|--------|
| **RTO** (tiempo de restauración del servicio API) | Objetivo: inferior a 1 h (aplicación); inferior a 4 h si hace falta reprovisionar entorno | Depende del plan PaaS y personal on-call. |
| **RPO** (pérdida máxima de datos aceptada) | Alinear con **backups de Postgres** (Railway plugin / Supabase PITR) | Ver contrato del proveedor; no sustituye pruebas de restore. |
| **Liveness vs readiness** | `GET /live` (proceso vivo), `GET /health` (Supabase + Redis), `GET /health/deep` (capa negocio + opcionales) | Ver `docs/operations/health_recovery.md`. |

Los importes económicos de valoración M&A en el roadmap son **narrativa**; los números anteriores son **objetivos técnicos** a validar con el proveedor de hosting.

## 3. Detección y observabilidad

1. **Sentry** (`SENTRY_DSN` backend, `NEXT_PUBLIC_SENTRY_DSN` frontend): errores no capturados, trazas muestreadas (`SENTRY_TRACES_SAMPLE_RATE`). `release` se rellena desde `APP_RELEASE` o SHA de CI (`RAILWAY_GIT_COMMIT_SHA` / `VERCEL_GIT_COMMIT_SHA`).
2. **Logs JSON** (`http_access`): campo `request_id` y cabecera `X-Request-ID` para correlación con Sentry y tickets.
3. **Discord / webhook** (`DISCORD_WEBHOOK_URL`): alertas críticas desde `AlertService` y fallos de `GET /health` (readiness).
4. **Healthchecks de plataforma**: Railway `healthcheckPath` = `/live` (despliegue rápido); monitoreo sintético externo recomendado sobre `/health` o `/health/deep` con `Host` permitido.

## 4. Escenarios y respuesta

### 4.1 Pérdida de Redis

- **Síntomas:** `checks.redis.ok=false` en `/health`; colas ARQ paradas; rate limit en memoria por proceso (si aplica).
- **Acción:** restaurar instancia Redis, verificar `REDIS_URL`, reiniciar `worker` y `backend`. Ver `health_recovery.md` §2–3.

### 4.2 Pérdida de Supabase / PostgREST

- **Síntomas:** `checks.supabase.ok=false`; errores 5xx masivos; auth roto.
- **Acción:** estado del proveedor Supabase; validar URL y claves; si es incidente regional, seguir comunicados oficiales y activar página de estado al cliente si existe.

### 4.3 Corrupción o brecha en cadena VeriFactu

- **Prioridad:** máxima (riesgo fiscal).
- **Acción:** **no** aplicar parches manuales a hashes en producción sin procedimiento documentado; usar herramientas de reparación/auditoría del repo (`verifactu_chain_repair`, tests de compliance) y escalado a responsable fiscal.

### 4.4 Compromiso de secretos

- Rotación inmediata siguiendo `README_SECURITY.md` y `scripts/rotate_secrets.py` (empezar con `--dry-run`).
- Invalidar sesiones si afecta a JWT/Fernet; revisar webhooks (Stripe, GoCardless) por firma.

### 4.5 Pérdida total de región (hipótesis)

- Recrear servicios en región alternativa desde Terraform / Railway / Vercel según `docs/INFRASTRUCTURE.md`.
- Restaurar Postgres desde backup; reapuntar `DATABASE_URL` y secretos.
- Prueba documentada de **restore** al menos anual (tabla de evidencias para DD).

## 5. Roles y comunicación

| Rol | Responsabilidad |
|-----|-----------------|
| **On-call técnico** | Triaje Sentry + logs, ejecución de runbooks, escalado. |
| **Producto / legal** | Comunicación a clientes si hay exposición de datos o SLA contractual (`docs/legal/SLA.md`). |

## 6. Verificación periódica

- [ ] Restore de Postgres en entorno **no productivo** documentado (fecha + resultado).
- [ ] `GET /health/deep` verde en staging tras cada despliegue mayor.
- [ ] Alertas de prueba a Discord / Sentry sin PII en payload.

## 7. Referencias en repo

- `docs/operations/health_recovery.md` — recuperación en 5 minutos.
- `README_SECURITY.md` — secretos y rotación.
- `docs/INFRASTRUCTURE.md` — Railway, Terraform, variables.
- `backend/docs/FISCAL_PERSISTENCE.md` — persistencia fiscal y cadena.
