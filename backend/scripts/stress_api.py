#!/usr/bin/env python3
"""Stress test concurrente para OCR gastos.

Ejemplo:
    python scripts/stress_api.py \
      --base-url http://127.0.0.1:8000 \
      --image ./fixtures/ticket.jpg \
      --concurrency 20 \
      --token "$JWT"
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from pathlib import Path

import httpx


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stress test OCR endpoint /api/v1/gastos/ocr")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL API FastAPI")
    parser.add_argument("--image", required=True, help="Ruta a imagen ticket")
    parser.add_argument("--token", default="", help="JWT bearer opcional")
    parser.add_argument("--concurrency", type=int, default=20, help="Número de requests concurrentes")
    parser.add_argument("--timeout", type=float, default=45.0, help="Timeout en segundos por request")
    return parser.parse_args()


async def _one_call(
    client: httpx.AsyncClient,
    *,
    idx: int,
    endpoint: str,
    image_bytes: bytes,
    filename: str,
    headers: dict[str, str],
) -> tuple[int, float, str]:
    started = time.perf_counter()
    files = {
        "evidencia": (filename, image_bytes, "image/jpeg"),
    }
    try:
        res = await client.post(endpoint, files=files, headers=headers)
        elapsed = (time.perf_counter() - started) * 1000
        return idx, elapsed, f"{res.status_code}"
    except Exception as exc:  # pragma: no cover - diagnóstico en runtime
        elapsed = (time.perf_counter() - started) * 1000
        return idx, elapsed, f"EXC:{exc.__class__.__name__}"


async def _run() -> int:
    args = _parse_args()
    image_path = Path(args.image).expanduser().resolve()
    if not image_path.exists():
        raise SystemExit(f"Imagen no encontrada: {image_path}")

    base = args.base_url.rstrip("/")
    endpoint = f"{base}/api/v1/gastos/ocr"
    image_bytes = image_path.read_bytes()
    headers = {"Accept": "application/json"}
    if args.token.strip():
        headers["Authorization"] = f"Bearer {args.token.strip()}"

    print(f"Endpoint: {endpoint}")
    print(f"Imagen: {image_path.name} ({len(image_bytes)} bytes)")
    print(f"Concurrencia: {args.concurrency}")

    timeout = httpx.Timeout(args.timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [
            _one_call(
                client,
                idx=i + 1,
                endpoint=endpoint,
                image_bytes=image_bytes,
                filename=image_path.name,
                headers=headers,
            )
            for i in range(args.concurrency)
        ]
        results = await asyncio.gather(*tasks)

    by_status: dict[str, int] = {}
    timings = []
    for _idx, ms, status in results:
        timings.append(ms)
        by_status[status] = by_status.get(status, 0) + 1

    ok = sum(v for k, v in by_status.items() if k.startswith("2"))
    fail = args.concurrency - ok
    p95 = statistics.quantiles(timings, n=20)[-1] if len(timings) >= 20 else max(timings)
    print("\n=== RESULTADOS ===")
    print(f"OK: {ok} | FAIL: {fail}")
    print(f"latency_ms min={min(timings):.1f} avg={statistics.mean(timings):.1f} p95={p95:.1f} max={max(timings):.1f}")
    print("status_count:", by_status)

    # Exit code no-cero si hubo errores de red/HTTP no 2xx.
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
