from __future__ import annotations

from uuid import UUID

import pytest

from app.api import deps


class _FacturaTenantChain:
    def __init__(self, factura_id: str, empresa_id: str) -> None:
        self._factura_id = factura_id
        self._empresa_id = empresa_id
        self._id_filter: str | None = None
        self._empresa_filter: str | None = None

    def select(self, *_args: object) -> "_FacturaTenantChain":
        return self

    def eq(self, col: str, val: object) -> "_FacturaTenantChain":
        if col == "id":
            self._id_filter = str(val)
        elif col == "empresa_id":
            self._empresa_filter = str(val)
        return self

    def limit(self, *_args: object) -> "_FacturaTenantChain":
        return self

    def execute(self) -> object:
        ok = self._id_filter == self._factura_id and self._empresa_filter == self._empresa_id
        rows = [{"id": self._factura_id, "empresa_id": self._empresa_id}] if ok else []

        class _R:
            data = rows

        return _R()


class _TenantDb:
    def __init__(self, factura_id: str, empresa_id: str) -> None:
        self._factura_id = factura_id
        self._empresa_id = empresa_id

    def table(self, name: str) -> _FacturaTenantChain:
        if name != "facturas":
            raise AssertionError(f"Tabla inesperada en test submit-final: {name}")
        return _FacturaTenantChain(self._factura_id, self._empresa_id)

    async def execute(self, query: object) -> object:
        return query.execute()


def _request_headers(client, idem_key: str) -> dict[str, str]:
    base = {k: v for k, v in client.headers.items()}
    base["Idempotency-Key"] = idem_key
    base["Host"] = "app.ablogistics-os.com"
    return base


@pytest.mark.asyncio
async def test_submit_final_verifactu_accepted(client, monkeypatch: pytest.MonkeyPatch) -> None:
    factura_id = "11111111-1111-1111-1111-111111111111"
    from tests.conftest import _resolve_seed_empresa_id

    empresa_id = str(_resolve_seed_empresa_id())
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_db] = lambda: _TenantDb(factura_id, empresa_id)

    async def _ok(self: object, *, factura_id: UUID) -> dict[str, object]:
        assert str(factura_id) == "11111111-1111-1111-1111-111111111111"
        return {
            "factura_id": str(factura_id),
            "aeat_sif_estado": "aceptado",
            "estado_verifactu": "ENVIADA",
            "csv": "CSV-OK-123",
            "codigo_error": None,
            "descripcion_error": None,
            "http_status": 200,
            "huella": "A" * 64,
        }

    monkeypatch.setattr("app.api.v1.verifactu.VerifactuService.submit_invoice_to_aeat", _ok)
    try:
        res = await client.post(
            f"/api/v1/verifactu/submit-final/{factura_id}",
            headers=_request_headers(client, "test-submit-final-accepted"),
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["aeat_sif_estado"] == "aceptado"
        assert body["estado_verifactu"] == "ENVIADA"
        assert body["csv"] == "CSV-OK-123"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_submit_final_verifactu_rejected_maps_200_payload(client, monkeypatch: pytest.MonkeyPatch) -> None:
    factura_id = "22222222-2222-2222-2222-222222222222"
    from tests.conftest import _resolve_seed_empresa_id

    empresa_id = str(_resolve_seed_empresa_id())
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_db] = lambda: _TenantDb(factura_id, empresa_id)

    async def _rejected(self: object, *, factura_id: UUID) -> dict[str, object]:
        return {
            "factura_id": str(factura_id),
            "aeat_sif_estado": "rechazado",
            "estado_verifactu": "PENDIENTE_CORRECCION",
            "csv": None,
            "codigo_error": "AEAT_HASH_MISMATCH",
            "descripcion_error": "Huella no coincide",
            "http_status": 200,
            "huella": "B" * 64,
        }

    monkeypatch.setattr("app.api.v1.verifactu.VerifactuService.submit_invoice_to_aeat", _rejected)
    try:
        res = await client.post(
            f"/api/v1/verifactu/submit-final/{factura_id}",
            headers=_request_headers(client, "test-submit-final-rejected"),
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["aeat_sif_estado"] == "rechazado"
        assert body["estado_verifactu"] == "PENDIENTE_CORRECCION"
        assert body["codigo_error"] == "AEAT_HASH_MISMATCH"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_submit_final_verifactu_timeout_returns_503(client, monkeypatch: pytest.MonkeyPatch) -> None:
    factura_id = "33333333-3333-3333-3333-333333333333"
    from tests.conftest import _resolve_seed_empresa_id

    empresa_id = str(_resolve_seed_empresa_id())
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_db] = lambda: _TenantDb(factura_id, empresa_id)

    async def _timeout(self: object, *, factura_id: UUID) -> dict[str, object]:
        raise RuntimeError("Connection timeout")

    monkeypatch.setattr("app.api.v1.verifactu.VerifactuService.submit_invoice_to_aeat", _timeout)
    try:
        res = await client.post(
            f"/api/v1/verifactu/submit-final/{factura_id}",
            headers=_request_headers(client, "test-submit-final-timeout"),
        )
        assert res.status_code == 503, res.text
        assert "timeout" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_submit_final_verifactu_returns_404_for_other_tenant(client) -> None:
    factura_id = "44444444-4444-4444-4444-444444444444"
    from tests.conftest import _resolve_seed_empresa_id

    empresa_id = str(_resolve_seed_empresa_id())
    # La DB fake solo expone otra factura distinta para forzar mismatch de tenant/resource.
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_db] = lambda: _TenantDb(
        "99999999-9999-9999-9999-999999999999", empresa_id
    )
    try:
        res = await client.post(
            f"/api/v1/verifactu/submit-final/{factura_id}",
            headers=_request_headers(client, "test-submit-final-tenant-404"),
        )
        assert res.status_code == 404, res.text
    finally:
        app.dependency_overrides.clear()
