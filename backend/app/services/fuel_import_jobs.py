"""Importación combustible en segundo plano (memoria + progreso), sin cola externa."""

from __future__ import annotations

import asyncio
import inspect
import time
import uuid
from dataclasses import asdict
from typing import Any

from app.db import supabase as supabase_db
from app.services.combustible_service import importar_combustible_csv
from app.services.gastos_service import GastosService

MAX_FUEL_IMPORT_JOB_BYTES = 12 * 1024 * 1024
_JOB_TTL_SEC = 30 * 60

_jobs_lock = asyncio.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def _prune_jobs() -> None:
    now = time.time()
    dead: list[str] = []
    for jid, row in _jobs.items():
        if now - float(row.get("created_at", 0)) > _JOB_TTL_SEC:
            dead.append(jid)
    for jid in dead:
        _jobs.pop(jid, None)


async def create_fuel_import_job(
    *,
    empresa_id: str,
    username_empleado: str,
    access_token: str,
    raw: bytes,
    filename: str,
) -> str:
    if len(raw) > MAX_FUEL_IMPORT_JOB_BYTES:
        raise ValueError(
            f"Archivo demasiado grande para importación en segundo plano (máx. {MAX_FUEL_IMPORT_JOB_BYTES // (1024 * 1024)} MB)."
        )
    job_id = str(uuid.uuid4())
    async with _jobs_lock:
        _prune_jobs()
        _jobs[job_id] = {
            "empresa_id": str(empresa_id),
            "username_empleado": str(username_empleado),
            "access_token": str(access_token),
            "raw": raw,
            "filename": filename or "import.csv",
            "status": "queued",
            "progress": 0,
            "created_at": time.time(),
            "result": None,
            "error": None,
        }
    return job_id


async def get_fuel_import_job(*, job_id: str, empresa_id: str) -> dict[str, Any] | None:
    async with _jobs_lock:
        _prune_jobs()
        row = _jobs.get(job_id)
        if not row:
            return None
        if str(row.get("empresa_id")) != str(empresa_id):
            return None
        return {
            "job_id": job_id,
            "status": row.get("status"),
            "progress": int(row.get("progress") or 0),
            "result": row.get("result"),
            "error": row.get("error"),
        }


async def _emit_progress(job_id: str, cur: int, tot: int) -> None:
    tot = max(int(tot), 1)
    pct = min(99, int(100 * int(cur) / tot))
    async with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["progress"] = pct


async def run_fuel_import_job(job_id: str) -> None:
    async with _jobs_lock:
        row = _jobs.get(job_id)
        if not row:
            return
        token = str(row.pop("access_token", "") or "")
        empresa_id = str(row["empresa_id"])
        username = str(row["username_empleado"])
        raw = row["raw"]
        filename = str(row["filename"])
        row["status"] = "running"
        row["progress"] = 1

    db = await supabase_db.get_supabase(jwt_token=token)
    raw_client = getattr(db, "_client", None)

    async def on_progress(cur: int, tot: int) -> None:
        await _emit_progress(job_id, cur, tot)

    try:

        async def _cb(cur: int, tot: int) -> None:
            await on_progress(cur, tot)

        svc = GastosService(db)
        out = await importar_combustible_csv(
            raw=raw,
            filename=filename,
            empresa_id=empresa_id,
            username_empleado=username,
            db=db,
            gastos_service=svc,
            dry_run=False,
            on_progress=_cb,
        )
        payload = asdict(out)
        async with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "completed"
                _jobs[job_id]["progress"] = 100
                _jobs[job_id]["result"] = payload
                _jobs[job_id]["raw"] = b""
    except Exception as exc:
        async with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = str(exc)
                _jobs[job_id]["raw"] = b""
    finally:
        if raw_client is not None:
            try:
                closer = getattr(raw_client, "aclose", None)
                if closer is not None:
                    out = closer()
                    if inspect.iscoroutine(out):
                        await out
            except Exception:
                pass
