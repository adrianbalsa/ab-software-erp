#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="docker-compose.prod.yml"

# Services that we can safely roll back by image tag.
ROLLBACK_IMAGES=(
  "redis:7-alpine|redis:stable"
  "abl-backend:prod|abl-backend:stable"
  "abl-frontend:prod|abl-frontend:stable"
  "caddy:2-alpine|caddy:stable"
  "cloudflare/cloudflared:latest|cloudflare/cloudflared:stable"
)

cd "${ROOT_DIR}"

send_emergency_alert() {
  local subject="$1"
  local body="$2"

  if SUBJECT="${subject}" BODY="${body}" PYTHONPATH="${ROOT_DIR}/backend" python3 -c "import os; from app.services.alert_service import send_critical_alert; send_critical_alert(os.environ['SUBJECT'], os.environ['BODY'])" >/dev/null 2>&1; then
    echo "==> Emergency alert sent via alert_service."
  else
    echo "WARNING: Failed to send emergency alert via alert_service."
  fi
}

tag_stable_images() {
  echo "==> Tagging current images as stable..."
  for mapping in "${ROLLBACK_IMAGES[@]}"; do
    local source_image="${mapping%%|*}"
    local stable_image="${mapping##*|}"
    if docker image inspect "${source_image}" >/dev/null 2>&1; then
      docker tag "${source_image}" "${stable_image}"
      echo "Tagged ${source_image} -> ${stable_image}"
    else
      echo "WARNING: Source image ${source_image} not found; skipping stable tag."
    fi
  done
}

rollback_to_stable() {
  local rollback_override
  rollback_override="$(mktemp)"

  cat > "${rollback_override}" <<'EOF'
services:
  redis:
    image: redis:stable
  backend:
    image: abl-backend:stable
  frontend:
    image: abl-frontend:stable
  caddy:
    image: caddy:stable
  cloudflared:
    image: cloudflare/cloudflared:stable
  sentinel-watchdog:
    image: abl-backend:stable
EOF

  echo "==> Re-deploying using stable image tags..."
  docker compose -f "${COMPOSE_FILE}" -f "${rollback_override}" down --remove-orphans
  docker compose -f "${COMPOSE_FILE}" -f "${rollback_override}" up -d --no-build
  rm -f "${rollback_override}"
}

echo "==> Checking environment file..."
if [[ ! -f ".env" ]]; then
  echo "ERROR: .env file not found in ${ROOT_DIR}"
  exit 1
fi

tag_stable_images

echo "==> Updating code from origin/main..."
git pull origin main

echo "==> Stopping current production containers..."
docker compose -f "${COMPOSE_FILE}" down --remove-orphans

echo "==> Building and starting production containers..."
docker compose -f "${COMPOSE_FILE}" up -d --build

echo "==> Waiting for services to warm up..."
sleep 10

echo "==> Verifying health endpoint..."
health_status="$(curl --silent --show-error --output /dev/null --write-out "%{http_code}" "http://localhost/api/health" || true)"
if [[ "${health_status}" == "200" ]]; then
  echo "Deployment completed successfully: health check passed."
  echo "==> Pruning old Docker images..."
  docker image prune -f
else
  echo "CRITICAL: Health check failed at http://localhost/api/health (status=${health_status}). Triggering rollback..."
  rollback_to_stable
  send_emergency_alert \
    "CRITICAL deployment rollback executed" \
    "Healthcheck failed (status=${health_status}) after deploy in ${ROOT_DIR}. Rolled back to stable images."
  exit 1
fi
