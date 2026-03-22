# Stress test con k6 (API AB Logistics OS)

Script: `stress_test.js` — 50 usuarios virtuales (VUs) durante 30 s, alternando:

- `GET /health/status` (sin autenticación; ejerce la capa de salud / DB)
- `GET /finance/dashboard` (requiere `Authorization: Bearer <JWT>`; consultas de negocio vía pool)

## Instalar k6

**macOS (Homebrew)**

```bash
brew install k6
```

**Linux (Debian/Ubuntu y otros)**  
Sigue la [guía oficial de instalación de k6](https://grafana.com/docs/k6/latest/set-up/install-k6/) (paquete `.deb`, `.rpm`, o binario).

**Windows (Chocolatey)**

```powershell
choco install k6
```

**Comprobar**

```bash
k6 version
```

## Ejecutar el test

Desde este directorio (o con ruta al `.js`):

```bash
cd backend/tests/k6
```

1. Arranca la API (p. ej. `uvicorn` contra el entorno que quieras medir, con PgBouncer delante si aplica).

2. Obtén un JWT válido (mismo que usa el front), por ejemplo:

   ```bash
   export K6_JWT="$(curl -s -X POST 'http://127.0.0.1:8000/auth/login' \
     -H 'Content-Type: application/x-www-form-urlencoded' \
     --data 'username=TU_USER&password=TU_PASS' | jq -r .access_token)"
   ```

3. Lanza k6:

   ```bash
   API_BASE_URL=http://127.0.0.1:8000 k6 run stress_test.js
   ```

   Si el token no está en el entorno:

   ```bash
   API_BASE_URL=http://127.0.0.1:8000 K6_JWT="$K6_JWT" k6 run stress_test.js
   ```

## Leer el resumen (métricas clave)

Al finalizar, k6 imprime un resumen. Lo más útil para rendimiento y errores:

| Métrica | Qué indica |
|--------|------------|
| **`http_req_duration`** | Tiempos de respuesta. Revisa **`p(95)`** y **`avg`** como referencia de latencia bajo carga. |
| **`http_req_failed`** | Ratio entre 0 y 1 (o porcentaje en la salida). Indica fallos HTTP o de red. Debe mantenerse **bajo**; el script tiene umbral `< 10%` como guía. |
| **`http_reqs`** | Total de peticiones y **tasa (req/s)** — capacidad observada del endpoint bajo el escenario. |
| **`checks`** | Porcentaje de comprobaciones `check()` superadas (p. ej. status 200). Si falla sin subir mucho `http_req_failed`, revisa códigos concretos (401 en `/finance` sin JWT). |

Los **`tags`** del script (`GET /health/status`, `GET /finance/dashboard`) permiten, en versiones recientes de k6, desglosar latencias por nombre en el informe o exportar a InfluxDB/Grafana para series temporales.

### ¿Está PgBouncer haciendo bien su trabajo?

PgBouncer **multiplexa** conexiones de cliente sobre un pool pequeño hacia Postgres. En un stress razonable deberías observar:

- **`p(95)` estable** y sin picos “en diente de sierra” continuos si el pool y `default_pool_size` están dimensionados; picos aislados pueden ser cold start o consultas pesadas.
- **`http_req_failed` cercano a 0**; subidas bruscas pueden indicar **agotamiento de conexiones** (`too many clients`), **timeouts** al esperar slot en el pool, o caída de Postgres/PgBouncer.
- Comparar **misma carga** con conexión **directa a Postgres** frente a **vía PgBouncer** (misma API, mismo `DATABASE_URL` o host alternativo): si con PgBouncer la **tasa de req/s** es similar o mayor y la latencia comparable, el pool suele estar amortiguando bien el fan-in de la API.

Señales de que conviene revisar PgBouncer o el pool:

- Muchos **5xx** o timeouts en el cliente mientras el CPU de la API es bajo (cola en el pool).
- Logs de PgBouncer con **“no more connections”** / **waiting clients** sostenidos.
- Latencia que crece linealmente con los VUs sin estabilizarse (saturación).

Ajusta `max_client_conn`, `default_pool_size` y límites en Postgres (`max_connections`) de forma coordinada; el test k6 sirve para **reproducir** carga antes de cambiar producción.

## Umbrales en el script

El archivo define `thresholds` de ejemplo (`p(95) < 5 s`, `http_req_failed < 10%`). Adáptalos a tu SLA y entorno (staging vs producción).
