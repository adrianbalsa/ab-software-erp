"""Generate a short-lived owner JWT for local smoke tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt


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
    secret = read_env_value(env_path, "JWT_SECRET_KEY")

    if not secret:
        print("ERROR: JWT_SECRET_KEY no encontrada en .env")
        return 1

    now = datetime.now(timezone.utc)
    payload = {
        "sub": "admin-test",
        "role": "owner",
        "tenant_id": "bunker-test-tenant",
        "exp": now + timedelta(hours=1),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
