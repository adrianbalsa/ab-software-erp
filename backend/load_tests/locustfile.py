"""
Pruebas de carga AB Logistics OS (Locust).

Rate limiting (Redis + limits) y concurrencia en PostgreSQL/Supabase:
--------------------------------------------------------------------
Al ejecutar con muchos usuarios concurrentes (p. ej. 100), lo esperado es:
  - Mayoría de peticiones autenticadas con **200 OK** en lecturas/escrituras válidas.
  - Eventualmente **429 Too Many Requests** en endpoints protegidos por el
    SlowAPI (100/min por IP) y ``AuthLoginRateLimitMiddleware`` (5/min en login/refresh).

Eso indica que Redis está aplicando el tope y se evita saturar la base de datos
con tráfico abusivo. Si nunca aparece 429 con carga muy alta, revisar ``REDIS_URL``,
``limits`` y la configuración del middleware en entorno de pruebas.

Ejecución: ver ``README_STRESS.md`` en la raíz del backend.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from uuid import UUID

from locust import HttpUser, between, task


def _auth_login_path() -> str:
    """
    OpenAPI ``tokenUrl`` y el router real usan ``/auth/login`` con
    ``application/x-www-form-urlencoded``. No existe ``/api/v1/auth/login`` montado
    en ``main.py``; si añades un alias en API Gateway, define ``LOCUST_AUTH_LOGIN_PATH``.
    """
    return os.environ.get("LOCUST_AUTH_LOGIN_PATH", "/auth/login")


class LogisticsUser(HttpUser):
    """Usuario virtual: login una vez, luego mezcla lectura intensiva, escritura y agregados."""

    wait_time = between(1, 3)

    def on_start(self) -> None:
        self._token: str | None = None
        self._cliente_id: str | None = None

        username = os.environ.get("LOCUST_USERNAME", "test_owner@ablogistics.com")
        password = os.environ.get("LOCUST_PASSWORD", "password123")

        login_path = _auth_login_path()
        with self.client.post(
            login_path,
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            catch_response=True,
            name=f"{login_path} [login]",
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"login failed: {resp.status_code}")
                return
            try:
                data = resp.json()
            except Exception as exc:  # noqa: BLE001
                resp.failure(f"login JSON: {exc}")
                return
            token = data.get("access_token")
            if not token:
                resp.failure("login response sin access_token")
                return
            self._token = str(token)
            self.client.headers.update({"Authorization": f"Bearer {self._token}"})

        # UUID de cliente real del tenant (necesario para POST /api/v1/portes/)
        with self.client.get("/clientes/", catch_response=True, name="/clientes/ [prefetch]") as cr:
            if cr.status_code != 200:
                cr.failure(f"clientes prefetch: {cr.status_code}")
                return
            try:
                rows = cr.json()
            except Exception as exc:  # noqa: BLE001
                cr.failure(f"clientes JSON: {exc}")
                return
            if isinstance(rows, list) and rows:
                cid = rows[0].get("id")
                if cid:
                    self._cliente_id = str(cid)

    @task(3)
    def poll_live_tracking(self) -> None:
        """Lectura intensiva (simula polling de mapa en vivo)."""
        self.client.get("/api/v1/flota/live-tracking", name="/api/v1/flota/live-tracking")

    @task(1)
    def create_porte(self) -> None:
        """Escritura: crea un porte mínimo válido (requiere cliente en BD)."""
        if not self._cliente_id:
            return
        try:
            UUID(self._cliente_id)
        except ValueError:
            return

        # Fecha en ventana válida; origen/destino cortos para no inflar payloads
        payload = {
            "cliente_id": self._cliente_id,
            "fecha": str(date.today() + timedelta(days=1)),
            "origen": "LoadTest Origen",
            "destino": "LoadTest Destino",
            "km_estimados": 120.0,
            "bultos": 1,
            "precio_pactado": 199.99,
        }
        self.client.post("/api/v1/portes/", json=payload, name="/api/v1/portes/ [POST]")

    @task(1)
    def treasury_cash_flow(self) -> None:
        """Consulta agregada (tesorería / cash-flow)."""
        self.client.get("/api/v1/treasury/cash-flow", name="/api/v1/treasury/cash-flow")
