"""Fast Discord webhook smoke test without starting FastAPI."""

from __future__ import annotations

from pathlib import Path

import httpx


def read_env_value(env_path: Path, key: str) -> str | None:
    if not env_path.exists():
        return None

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        k, v = line.split("=", 1)
        if k.strip() != key:
            continue

        value = v.strip()
        if (
            (value.startswith('"') and value.endswith('"'))
            or (value.startswith("'") and value.endswith("'"))
        ):
            value = value[1:-1]
        return value

    return None


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / ".env"
    webhook_url = read_env_value(env_path, "ALERT_WEBHOOK_URL")

    if not webhook_url:
        print("ERROR: ALERT_WEBHOOK_URL no encontrada en .env")
        return 1

    payload = {
        "content": "🚀 **¡BÚNKER HABLANDO!** Conexión directa desde script validada. Próximo paso: Arreglar Pango."
    }

    try:
        response = httpx.post(webhook_url, json=payload, timeout=15.0)
    except Exception as exc:  # pragma: no cover - script temporal
        print(f"ERROR enviando webhook: {exc}")
        return 1

    print(f"Discord status_code={response.status_code}")
    if response.text.strip():
        print(f"Discord body={response.text.strip()}")

    if response.status_code == 204:
        print("OK: Discord respondió 204 No Content.")
        return 0

    print("ERROR: Discord no devolvió 204.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
