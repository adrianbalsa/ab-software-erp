# DEPLOY-002: dominios finales, TLS, CORS y Redis (Fase 3.2)

Objetivo: cerrar **superficie de ataque** y **rutas públicas** antes del tráfico real: `app.*` / `api.*`, `TrustedHostMiddleware`, CORS acotado y Redis con **TLS** (y Sentinel si aplica).

## Referencias canónicas

- Topología y variables: `docs/operations/OPS_001_TOPOLOGIA_PLATAFORMA.md` (dominios § Dominios y DNS).
- Railway/Vercel/DNS: `docs/DEPLOYMENT.md`.
- Redis HA / cola / Sentinel: `docs/operations/REDIS_001_HA_BILLING_QUEUE.md`.
- Comprobación local de flags (sin DNS): `backend/scripts/check_deploy_infra_readiness.py`.

## 1. DNS y certificados TLS

Sustituir `<dominio>` y `<api_host>` por valores reales.

```bash
# Resolución
dig +short app.<dominio> A
dig +short app.<dominio> CNAME
dig +short api.<dominio> CNAME

# Cadena TLS (sustituir host)
echo | openssl s_client -servername api.<dominio> -connect api.<dominio>:443 2>/dev/null | openssl x509 -noout -subject -dates -issuer
```

Criterio: certificado emitido para el **hostname** que ve el cliente; no warnings de nombre en navegador ni en `curl`.

## 2. API pública (Railway)

```bash
curl -fsSI "https://api.<dominio>/live"
curl -fsSI "https://api.<dominio>/health"
curl -fsSI "https://api.<dominio>/health/deep"
```

Preflight CORS (sustituir origen del front oficial):

```bash
curl -fsSI -X OPTIONS "https://api.<dominio>/health" \
  -H "Origin: https://app.<dominio>" \
  -H "Access-Control-Request-Method: GET"
```

Comprobar cabeceras `access-control-allow-origin` acordes a la política (no `*` en credenciales).

## 3. `ALLOWED_HOSTS` y `CORS_ALLOW_ORIGINS`

En **Railway** (producción):

- `ENVIRONMENT=production`
- `ALLOWED_HOSTS`: lista explícita de hosts del API (coma). El código fusiona defaults oficiales + `API_PUBLIC_HOST` + env; no uses `*`.
- `CORS_ALLOW_ORIGINS` / `OFFICIAL_FRONTEND_ORIGIN`: solo HTTPS de dominios que controláis; revisar si `CORS_ALLOW_ORIGIN_REGEX` para previews Vercel sigue siendo aceptable.

Comprobación sin exponer secretos:

```bash
cd backend
PYTHONPATH=. python scripts/check_deploy_infra_readiness.py
PYTHONPATH=. python scripts/check_deploy_infra_readiness.py --strict
```

`--strict` en **`ENVIRONMENT=production`** trata cualquier advertencia (p. ej. `REDIS_URL` sin `rediss://`, `http://` en CORS) como error de salida; en desarrollo no fuerza código 2 por Redis vacío.

## 4. Redis TLS y HA

- **Railway Redis** suele exponer URL con esquema **`rediss://`** (TLS). El worker ARQ respeta TLS vía `RedisSettings.from_dsn` / `ssl=True` en Sentinel (`app/core/redis_config.py`).
- **Sentinel / réplicas:** seguir `REDIS_001_HA_BILLING_QUEUE.md` (`REDIS_SENTINEL_HOSTS`, `REDIS_SENTINEL_MASTER`).
- **Failover:** simulacro acordado con ventana (failover gestionado o reinicio nodo); validar que API y worker recuperan conexión y que la cola no queda bloqueada.

Cliente de prueba (si `redis-cli` con TLS disponible):

```bash
redis-cli -u "$REDIS_URL" PING
```

## 5. Smoke mínimo autenticado (manual)

Tras login o token de prueba:

- `GET` o `POST` de un endpoint con RBAC conocido (p. ej. facturas o dashboard).
- Confirmar **429** bajo abuso no afecta a otro tenant (rate limit multi-tenant, Fase 2.2).

## 6. Evidencia (no en git público)

| Artefacto | Notas |
|-----------|--------|
| Captura panel Vercel/Railway dominios + variables sensibles **ocultas** | |
| Salida redactada de `openssl s_client` / `curl -I` | |
| Resultado `check_golive_readiness.py --strict` contra URL real | |
| Nota de simulacro Redis (fecha, duración, resultado) | |

## Criterio de cierre (Fase 3.2)

App y API sirven en **dominios finales HTTPS**, `TrustedHost` + CORS acotados a orígenes controlados, Redis con **TLS** en URL de producción (y HA probado según política interna).
