# AB Logistics OS Backend - Producción Multi-Stage
# ---------------------------------------------------------

# --- Etapa 1: Builder ---
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencias de sistema necesarias para compilar paquetes de Python y psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Creamos entorno virtual para aislar las dependencias y copiarlo fácilmente
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
# Instalamos dependencias compilando wheels donde sea necesario
RUN pip install --no-cache-dir -r requirements.txt


# --- Etapa 2: Runtime Final ---
FROM python:3.12-slim-bookworm AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Librerías mínimas de runtime (ej. cliente PostgreSQL en C)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiamos entorno virtual desde el builder
COPY --from=builder /opt/venv /opt/venv

# Copiamos código fuente
COPY . .

# Usuario no privilegiado por seguridad
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin -c "Docker image user" appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# Salud operativa: PostgREST/Supabase vía GET /health (200 = ok, 503 = degradado)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Uvicorn optimizado (workers autoajustados mediante variables de entorno u opcionalmente hardcodeados, ej. 4)
# WEB_CONCURRENCY es detectado automáticamente por uvicorn / gunicorn. Por defecto pondremos 4.
ENV WEB_CONCURRENCY=4
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips='*'"]
