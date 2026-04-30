#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
DOMAIN="${DOMAIN:-}"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-180}"

if [[ -z "$DOMAIN" ]]; then
  echo "ERROR: Define DOMAIN (ej. export DOMAIN=ablogistics-os.com)" >&2
  exit 1
fi

if [[ -z "$ADMIN_EMAIL" ]]; then
  echo "ERROR: Define ADMIN_EMAIL (ej. export ADMIN_EMAIL=ops@ablogistics-os.com)" >&2
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "ERROR: No existe $COMPOSE_FILE en $ROOT" >&2
  exit 1
fi

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local elapsed=0

  until curl -kfsS "$url" >/dev/null 2>&1; do
    sleep 3
    elapsed=$((elapsed + 3))
    if [[ "$elapsed" -ge "$HEALTH_TIMEOUT_SECONDS" ]]; then
      echo "ERROR: timeout esperando healthcheck de $name en $url" >&2
      return 1
    fi
  done

  echo "OK: $name healthy ($url)"
}

echo "[1/5] Preparando rutas persistentes de certbot..."
mkdir -p infrastructure/certbot/conf/live/default infrastructure/certbot/www

if [[ ! -f infrastructure/certbot/conf/live/default/fullchain.pem ]] || [[ ! -f infrastructure/certbot/conf/live/default/privkey.pem ]]; then
  echo "[2/5] Generando certificado temporal autofirmado para bootstrap de Nginx..."
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout infrastructure/certbot/conf/live/default/privkey.pem \
    -out infrastructure/certbot/conf/live/default/fullchain.pem \
    -subj "/CN=${DOMAIN}"
fi

echo "[3/5] Levantando Nginx para responder challenge ACME..."
compose up -d nginx

echo "[4/5] Solicitando/renovando certificado Let's Encrypt para ${DOMAIN}..."
compose run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot \
  --email "$ADMIN_EMAIL" \
  --agree-tos \
  --no-eff-email \
  --non-interactive \
  -d "$DOMAIN"

mkdir -p infrastructure/certbot/conf/live/default
cp "infrastructure/certbot/conf/live/${DOMAIN}/fullchain.pem" "infrastructure/certbot/conf/live/default/fullchain.pem"
cp "infrastructure/certbot/conf/live/${DOMAIN}/privkey.pem" "infrastructure/certbot/conf/live/default/privkey.pem"

echo "[5/5] Levantando stack completo de producción..."
compose up -d --build --remove-orphans

wait_for_url "API" "https://127.0.0.1/health"
wait_for_url "Frontend" "https://127.0.0.1/"

echo "Despliegue finalizado correctamente para ${DOMAIN}."
