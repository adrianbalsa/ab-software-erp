from __future__ import annotations


async def test_public_compliance_pack(client) -> None:
    res = await client.get("/api/v1/public/compliance")
    assert res.status_code == 200
    body = res.json()
    assert body.get("compliance_pack_version")
    assert isinstance(body.get("subprocessors"), list)
    assert len(body["subprocessors"]) >= 1
    assert body.get("sla", {}).get("uptime_target_monthly_percent") == 99.9
    assert body.get("gdpr", {}).get("right_to_erasure", {}).get("path_template")
    assert body.get("security_contact_email") == "security@ablogistics-os.com"


async def test_security_txt_rfc9116(client) -> None:
    res = await client.get("/.well-known/security.txt")
    assert res.status_code == 200
    assert res.headers.get("content-type", "").startswith("text/plain")
    text = res.text
    assert "Contact: mailto:security@ablogistics-os.com" in text
    assert "Preferred-Languages:" in text
    assert "Expires:" in text
