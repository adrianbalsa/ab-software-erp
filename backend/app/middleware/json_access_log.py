from __future__ import annotations

import json
import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.log_sanitizer import mask_bearer_hint, mask_query_string, mask_subject_for_log
from app.core.security import decode_access_token_payload

_access_logger = logging.getLogger("http_access")


def _extract_auth_context(authorization: str | None) -> tuple[str | None, str | None]:
    """
    Devuelve (empresa_id, auth_subject) si el Bearer es un JWT válido de la app.
    Tokens Supabase Auth válidos pueden no incluir ``empresa_id``.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None, None
    token = authorization[7:].strip()
    if not token:
        return None, None
    try:
        payload = decode_access_token_payload(token)
        sub = payload.get("sub")
        eid = payload.get("empresa_id")
        return (
            str(eid) if eid is not None and str(eid).strip() else None,
            str(sub) if sub is not None else None,
        )
    except Exception:
        return None, None


class JsonAccessLogMiddleware(BaseHTTPMiddleware):
    """
    Una línea JSON por petición (consumo cómodo con Logflare / agregadores).
    """

    def __init__(self, app: Callable, *, service_name: str = "ab-logistics-api") -> None:
        super().__init__(app)
        self._service_name = service_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response: Response | None = None
        error_message: str | None = None
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            error_message = str(exc)
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            auth = request.headers.get("authorization")
            empresa_id, auth_subject = _extract_auth_context(auth)
            q_masked = mask_query_string(request.url.query)
            status = getattr(response, "status_code", 500) if response is not None else 500
            request_id = getattr(request.state, "request_id", None)
            entry = {
                "message": "http_access",
                "service": self._service_name,
                "method": request.method,
                "path": request.url.path,
                "status_code": status,
                "duration_ms": round(duration_ms, 2),
                "request_id": request_id,
                "empresa_id": empresa_id,
                "auth_subject_masked": mask_subject_for_log(auth_subject),
                "authorization": mask_bearer_hint(auth),
                "query_masked": q_masked,
            }
            if error_message:
                entry["error"] = error_message[:500]
            line = json.dumps(entry, ensure_ascii=False)
            if _access_logger.handlers:
                _access_logger.info(line)
            else:
                print(line, flush=True)
