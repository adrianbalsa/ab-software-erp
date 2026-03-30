#!/usr/bin/env bash
# Vista rápida del estado de salud de los contenedores del stack (Docker Compose).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! docker compose version &>/dev/null; then
  echo "Error: se requiere Docker Compose v2 (docker compose)." >&2
  exit 1
fi

echo "=== docker compose ps ==="
docker compose ps

echo ""
echo "=== Health por contenedor (docker inspect) ==="
ids=$(docker compose ps -q)
if [[ -z "${ids// }" ]]; then
  echo "(no hay contenedores en ejecución para este proyecto)"
  exit 0
fi

printf "%-45s %-14s %-10s\n" "CONTENEDOR" "HEALTH" "ESTADO"
printf "%-45s %-14s %-10s\n" "--------------------------------------------" "--------------" "----------"
while IFS= read -r id; do
  [[ -z "$id" ]] && continue
  name=$(docker inspect --format '{{.Name}}' "$id" | sed 's|^/||')
  state=$(docker inspect --format '{{.State.Status}}' "$id")
  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}(sin check){{end}}' "$id")
  printf "%-45s %-14s %-10s\n" "$name" "$health" "$state"
done <<< "$ids"

echo ""
echo "Detalle FailingStreak (si aplica):"
while IFS= read -r id; do
  [[ -z "$id" ]] && continue
  name=$(docker inspect --format '{{.Name}}' "$id" | sed 's|^/||')
  streak=$(docker inspect --format '{{if .State.Health}}{{.State.Health.FailingStreak}}{{else}}-{{end}}' "$id")
  last=$(docker inspect --format '{{if and .State.Health (index .State.Health.Log 0)}}{{(index .State.Health.Log 0).Output}}{{else}}-{{end}}' "$id" 2>/dev/null | head -c 120)
  if [[ "$streak" != "-" && "$streak" != "0" ]]; then
    echo "  $name failing_streak=$streak last=${last:-?}"
  fi
done <<< "$ids"
