#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="docker-compose.prod.yml"
HEALTHCHECK_URL="http://localhost/api/health"

cd "${ROOT_DIR}"

send_alert() {
  local subject="$1"
  local body="$2"

  if SUBJECT="${subject}" BODY="${body}" PYTHONPATH="${ROOT_DIR}/backend" python3 -c "import os; from app.services.alert_service import send_critical_alert; send_critical_alert(os.environ['SUBJECT'], os.environ['BODY'])" >/dev/null 2>&1; then
    echo "==> Alert sent via alert_service."
  else
    echo "WARNING: Failed to send alert via alert_service."
  fi
}

confirm_rollback() {
  local confirmation
  echo "WARNING: This will force production services to use :stable images."
  read -r -p "Proceed with MANUAL ROLLBACK? (y/n): " confirmation
  if [[ "${confirmation}" != "y" && "${confirmation}" != "Y" ]]; then
    echo "Rollback cancelled."
    exit 0
  fi
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

  echo "==> Re-deploying stack with stable images (no build)..."
  docker compose -f "${COMPOSE_FILE}" -f "${rollback_override}" down --remove-orphans
  docker compose -f "${COMPOSE_FILE}" -f "${rollback_override}" up -d --no-build
  rm -f "${rollback_override}"
}

echo "==> Checking environment file..."
if [[ ! -f ".env" ]]; then
  echo "ERROR: .env file not found in ${ROOT_DIR}"
  exit 1
fi

confirm_rollback

echo "==> Sending rollback alert..."
send_alert \
  "Manual Rollback initiated by administrator." \
  "Manual rollback started in ${ROOT_DIR}. Forcing docker-compose.prod.yml services to :stable tags."

rollback_to_stable

echo "==> Waiting for services to warm up..."
sleep 10

echo "==> Verifying health endpoint..."
health_status="$(curl --silent --show-error --output /dev/null --write-out "%{http_code}" "${HEALTHCHECK_URL}" || true)"
if [[ "${health_status}" == "200" ]]; then
  echo "Manual rollback completed successfully: stable version is healthy."
else
  echo "CRITICAL: Rollback health check failed at ${HEALTHCHECK_URL} (status=${health_status})."
  exit 1
fi
