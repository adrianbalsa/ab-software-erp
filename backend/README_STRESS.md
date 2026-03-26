# Pruebas de estrés con Locust (AB Logistics OS)

Valida **rate limiting** (Redis) y **concurrencia** contra PostgreSQL/Supabase sin tocar la lógica de negocio: el escenario dispara login, polling de flota, alta de portes y agregados de tesorería.

## Requisitos

- API levantada y accesible (por defecto `http://127.0.0.1:8000`).
- Redis configurado si quieres ver **429 Too Many Requests** bajo carga (mismo `REDIS_URL` que usa la app).
- Usuario de prueba existente con rol **owner** (por defecto `test_owner@ablogistics.com` / `password123`) y al menos **un cliente** en el tenant (para el POST de portes).

## Instalar Locust (solo entorno QA / local)

No se instala Locust en la imagen de producción. Usa un venv o máquina de carga:

```bash
cd backend
python -m venv .venv-loadtest
source .venv-loadtest/bin/activate   # Windows: .venv-loadtest\Scripts\activate
pip install -r requirements-loadtest.txt
```

## Ejecutar Locust (interfaz web)

Desde el directorio `backend` (o ajusta la ruta al `locustfile`):

```bash
locust -f load_tests/locustfile.py --host http://127.0.0.1:8000
```

Abre el navegador en **http://localhost:8089**, define número de usuarios y tasa de arranque, y lanza la prueba.

### Variables de entorno útiles

| Variable | Descripción |
|----------|--------------|
| `LOCUST_USERNAME` | Usuario login (default: `test_owner@ablogistics.com`) |
| `LOCUST_PASSWORD` | Contraseña (default: `password123`) |
| `LOCUST_AUTH_LOGIN_PATH` | Ruta de login (default: `/auth/login`; el backend no expone `/api/v1/auth/login`) |

Ejemplo:

```bash
export LOCUST_PASSWORD="tu_password_seguro"
locust -f load_tests/locustfile.py --host https://api.tu-dominio.com
```

## Qué observar

- **200** en la mayoría de peticiones con carga moderada.
- **429** en picos fuertes (p. ej. muchos usuarios concurrentes) confirma que el límite por IP/JWT está activo.
- **401** masivo: revisar credenciales o expiración de JWT (cada usuario virtual hace login en `on_start`).

## Documentación Locust

[https://docs.locust.io/](https://docs.locust.io/)
