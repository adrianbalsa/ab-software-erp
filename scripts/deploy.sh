#!/usr/bin/env bash
# AB Logistics OS — despliegue en VPS (Docker Compose producción + Cloudflare opcional)
#
# Uso:
#   ./scripts/deploy.sh deploy              # pull, build, up (perfil cloudflare si hay token)
#   ./scripts/deploy.sh deploy-rolling      # actualización por capas (menos downtime relativo)
#   ./scripts/deploy.sh validate            # docker compose config (requiere Docker; APP_DOMAIN/API_DOMAIN o .env)
#   ./scripts/deploy.sh validate-build      # validate + build de imágenes (sin up)
#   ./scripts/deploy.sh backup-env        # volcado CIFRADO de .env (requiere ENV_BACKUP_PASSWORD o GPG_PASSPHRASE)
#   ./scripts/deploy.sh env-audit         # listado de claves sensibles con valores redactados (sin secretos en claro)
#
# Variables opcionales:
#   COMPOSE_FILE   — por defecto docker-compose.prod.yml en la raíz del repo
#   GIT_REMOTE     — rama remota (default: origin)
#   GIT_BRANCH     — rama a desplegar (default: actual)
#   ENV_FILE       — ruta a .env (default: .env en raíz)
#   ENV_BACKUP_DIR — destino de backup-env (default: ./backups/env)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
COMPOSE_BASE=(docker compose -f "$COMPOSE_FILE")

# Activa perfil cloudflare si existe token (evita reinicios del contenedor sin token)
if [[ -f "$ENV_FILE" ]] && grep -qE '^CLOUDFLARE_TUNNEL_TOKEN=.+$' "$ENV_FILE" 2>/dev/null; then
  export COMPOSE_PROFILES="${COMPOSE_PROFILES:-cloudflare}"
elif [[ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]]; then
  export COMPOSE_PROFILES="${COMPOSE_PROFILES:-cloudflare}"
fi

compose() {
  "${COMPOSE_BASE[@]}" "$@"
}

cmd="${1:-deploy}"

require_compose_file() {
  [[ -f "$ROOT/$COMPOSE_FILE" ]] || {
    echo "No se encuentra $COMPOSE_FILE en $ROOT" >&2
    exit 1
  }
}

do_git_pull() {
  if [[ "${SKIP_GIT_PULL:-0}" == "1" ]]; then
    echo "[deploy] SKIP_GIT_PULL=1 — omitiendo git pull"
    return 0
  fi
  if [[ -d "$ROOT/.git" ]]; then
    git fetch "${GIT_REMOTE:-origin}" --prune
    local branch="${GIT_BRANCH:-}"
    if [[ -z "$branch" ]]; then
      branch="$(git rev-parse --abbrev-ref HEAD)"
    fi
    git pull --ff-only "${GIT_REMOTE:-origin}" "$branch"
  else
    echo "[deploy] Aviso: no hay repositorio git; omitiendo pull"
  fi
}

# Nota zero-downtime: Compose con réplica única implica ventana breve al recrear contenedor.
# Para HA real: Swarm/Kubernetes con replicas>1 o blue/green con dos proyectos Compose.
cmd_deploy() {
  require_compose_file
  do_git_pull
  echo "[deploy] build imágenes…"
  compose build --pull
  echo "[deploy] levantando stack…"
  compose up -d --remove-orphans
  compose ps
  echo "[deploy] OK. Health: API vía Caddy → curl -fsS -H \"Host: \$API_DOMAIN\" http://127.0.0.1:\${CADDY_HTTP_PORT:-8080}/ready"
}

# Actualiza backend → comprueba /ready → frontend → caddy → cloudflared (si perfil activo).
cmd_deploy_rolling() {
  require_compose_file
  do_git_pull
  echo "[deploy-rolling] build…"
  compose build --pull

  compose up -d --no-deps redis
  compose up -d --no-deps --build backend
  echo "[deploy-rolling] esperando salud del backend…"
  local tries=0
  while ! compose exec -T backend curl -fsS http://127.0.0.1:8000/ready >/dev/null 2>&1; do
    tries=$((tries + 1))
    if [[ "$tries" -gt 60 ]]; then
      echo "Timeout esperando backend healthy" >&2
      exit 1
    fi
    sleep 2
  done

  compose up -d --no-deps --build frontend
  sleep 5
  compose up -d --no-deps --build caddy
  sleep 3
  if [[ "${COMPOSE_PROFILES:-}" == *cloudflare* ]]; then
    compose up -d --no-deps cloudflared || true
  fi
  compose ps
  echo "[deploy-rolling] OK"
}

# Volcado cifrado de variables críticas (.env completo cifrado en disco).
cmd_backup_env() {
  [[ -f "$ENV_FILE" ]] || {
    echo "No existe $ENV_FILE" >&2
    exit 1
  }
  local dest="${ENV_BACKUP_DIR:-$ROOT/backups/env}"
  mkdir -p "$dest"
  local stamp
  stamp="$(date +%Y%m%d_%H%M%S)"
  umask 077

  if [[ -n "${ENV_BACKUP_PASSWORD:-}" ]]; then
    local out="$dest/.env.${stamp}.enc"
    openssl enc -aes-256-cbc -pbkdf2 -iter 100000 -salt \
      -in "$ENV_FILE" -out "$out" -pass "pass:${ENV_BACKUP_PASSWORD}"
    chmod 600 "$out"
    echo "Copia cifrada (openssl): $out"
    echo "Restaurar: openssl enc -aes-256-cbc -pbkdf2 -d -in $out -out .env.restored -pass pass:…"
  elif [[ -n "${GPG_PASSPHRASE:-}" ]]; then
    local out="$dest/.env.${stamp}.gpg"
    gpg --batch --yes --pinentry-mode loopback --passphrase "$GPG_PASSPHRASE" \
      --symmetric --cipher-algo AES256 -o "$out" "$ENV_FILE"
    chmod 600 "$out"
    echo "Copia cifrada (GPG): $out"
  else
    echo "Definir ENV_BACKUP_PASSWORD (recomendado, openssl) o GPG_PASSPHRASE para cifrar el volcado." >&2
    exit 1
  fi
}

# Auditoría: solo nombres de claves típicamente sensibles, valores redactados (no apto como backup).
cmd_env_audit() {
  [[ -f "$ENV_FILE" ]] || {
    echo "No existe $ENV_FILE" >&2
    exit 1
  }
  echo "# Volcado REDACTADO (sin secretos) — $(date -Iseconds)"
  local patterns='SUPABASE_|JWT_|SESSION_|PII_|STRIPE_|OPENAI_|CLOUDFLARE_|TUNNEL|REDIS_PASSWORD|DATABASE_URL|POSTGRES|GOCARDLESS|AUTH0|CLERK|RESEND_|SENTRY|FERNET|ENCRYPTION|API_KEY|SECRET|PASSWORD|TOKEN|PRIVATE'
  grep -E "^(${patterns})" "$ENV_FILE" 2>/dev/null | sed -E 's/(=).*/\1***REDACTED***/' || true
  echo "# Fin."
}

# Comprueba interpolación y sintaxis del compose (útil en VPS / CI).
cmd_validate() {
  require_compose_file
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker no está instalado o no está en PATH." >&2
    exit 1
  fi
  export APP_DOMAIN="${APP_DOMAIN:-app.validate.local}"
  export API_DOMAIN="${API_DOMAIN:-api.validate.local}"
  compose config --quiet
  echo "compose config: OK ($COMPOSE_FILE)"
}

cmd_validate_build() {
  cmd_validate
  compose build
  echo "compose build: OK"
}

case "$cmd" in
  deploy)
    cmd_deploy
    ;;
  deploy-rolling)
    cmd_deploy_rolling
    ;;
  backup-env)
    cmd_backup_env
    ;;
  env-audit)
    cmd_env_audit
    ;;
  validate)
    cmd_validate
    ;;
  validate-build)
    cmd_validate_build
    ;;
  *)
    echo "Comando desconocido: $cmd" >&2
    echo "Uso: $0 deploy | deploy-rolling | validate | validate-build | backup-env | env-audit" >&2
    exit 1
    ;;
esac
