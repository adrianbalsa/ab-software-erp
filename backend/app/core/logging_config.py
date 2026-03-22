"""
Rotación de logs en disco (evita crecimiento ilimitado de ficheros .log).

Activación: define ``LOG_FILE_PATH`` (ruta absoluta o relativa). Opcional:
``LOG_MAX_BYTES`` (default 10 MiB), ``LOG_BACKUP_COUNT`` (default 5).

Los logs de acceso JSON van al logger ``http_access`` (además de stdout si
``LOG_ACCESS_TO_STDOUT`` no es ``0``/``false``).
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys


def configure_app_logging() -> None:
    path = (os.getenv("LOG_FILE_PATH") or "").strip()
    if not path:
        return

    max_bytes = int(os.getenv("LOG_MAX_BYTES") or str(10 * 1024 * 1024))
    backup_count = int(os.getenv("LOG_BACKUP_COUNT") or "5")
    to_stdout = (os.getenv("LOG_ACCESS_TO_STDOUT") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )

    http_logger = logging.getLogger("http_access")
    http_logger.setLevel(logging.INFO)

    # Evitar duplicar handlers si ``create_app`` se invoca más de una vez (tests)
    if any(isinstance(h, logging.handlers.RotatingFileHandler) for h in http_logger.handlers):
        return

    fh = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter("%(message)s"))
    http_logger.addHandler(fh)

    if to_stdout:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(message)s"))
        http_logger.addHandler(sh)

    # No propagar a root (evita duplicados si root tiene handlers)
    http_logger.propagate = False
