#!/usr/bin/env bash
# Validación previa a despliegue: pytest (backend) + build del frontend.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "== Backend: pytest (requirements-dev) =="
cd "$ROOT/backend"
if ! python -c "import signxml, httpx" 2>/dev/null; then
  echo "Instalando dependencias: pip install -r requirements-dev.txt"
  python -m pip install -r requirements-dev.txt
fi
python -m pytest tests/ -q --tb=short "$@"

echo ""
echo "== Frontend: npm run build =="
cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  echo "Instalando dependencias npm..."
  npm ci 2>/dev/null || npm install
fi
npm run build

echo ""
echo "verify_integrity: OK"
