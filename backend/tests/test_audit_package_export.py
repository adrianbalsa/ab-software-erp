from __future__ import annotations

import io
import json
import zipfile

import pytest

from app.services.audit_package_export import build_audit_package_zip_bytes


def test_build_audit_package_zip_bytes_structure() -> None:
    raw = build_audit_package_zip_bytes()
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = set(zf.namelist())
    assert names == {"INDEX.md", "public_compliance_snapshot.json", "pricing_catalog.json", "security.txt"}


@pytest.mark.asyncio
async def test_export_audit_package_zip_owner(client) -> None:
    res = await client.get("/api/v1/export/audit-package")
    assert res.status_code == 200
    assert res.headers.get("content-type", "").startswith("application/zip")
    cd = res.headers.get("content-disposition", "")
    assert "attachment" in cd.lower()
    assert ".zip" in cd

    zf = zipfile.ZipFile(io.BytesIO(res.content))
    pricing = json.loads(zf.read("pricing_catalog.json").decode("utf-8"))
    plans = {p["plan_slug"]: p["eur_monthly"] for p in pricing["base_plans"]}
    assert plans["starter"] == 39
    assert plans["pro"] == 149
    assert plans["enterprise"] == 399
    assert len(pricing.get("addons", [])) == 3

    snap = json.loads(zf.read("public_compliance_snapshot.json").decode("utf-8"))
    assert snap.get("compliance_pack_version")
    assert snap.get("audit_package_generated_at_utc")
