#!/usr/bin/env sh
# Arranque explícito del worker ARQ (Railway / Railpack).
# No usar ``start.sh`` en la raíz de ``backend/``: Railpack lo detecta como proveedor "shell"
# y omite la instalación Python (ver documentación de Railpack).
set -eu
exec arq app.worker.WorkerSettings
