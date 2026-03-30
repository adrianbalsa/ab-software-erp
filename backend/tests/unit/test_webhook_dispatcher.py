import hashlib
import hmac

from app.core.webhook_dispatcher import build_ablogistics_signature_value, canonical_json_str


def test_canonical_json_stable():
    s = canonical_json_str({"b": 1, "a": 2})
    assert s == '{"a":2,"b":1}'


def test_ablogistics_signature_matches_hmac_of_body():
    secret = "s" * 32
    body = '{"a":1}'
    ts, header = build_ablogistics_signature_value(secret_key=secret, body_str=body)
    assert header.startswith(f"t={ts},v1=")
    expected = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    assert header == f"t={ts},v1={expected}"
