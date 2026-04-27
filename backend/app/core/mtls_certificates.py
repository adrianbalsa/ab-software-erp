from __future__ import annotations

import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import httpx
from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs12

from app.core.config import Settings, get_settings

CERT_EXPIRY_ALERT_THRESHOLDS_DAYS: tuple[int, ...] = (30, 15, 7)
_MAX_CERTIFICATES_IN_HEALTH = 25
_ALERT_THROTTLE_SECONDS = 12 * 60 * 60
_last_alert_sent_by_key: dict[str, float] = {}


def _certificate_common_name(cert: x509.Certificate) -> str | None:
    try:
        attrs = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
    except Exception:
        return None
    if not attrs:
        return None
    value = str(attrs[0].value).strip()
    return value or None


def _certificate_not_after_utc(cert: x509.Certificate) -> datetime:
    value = getattr(cert, "not_valid_after_utc", None)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return cert.not_valid_after.replace(tzinfo=timezone.utc)


def _load_certificate_from_p12(path: str, password: str | None) -> x509.Certificate:
    data = Path(path).read_bytes()
    pwd = password.encode("utf-8") if password else None
    _key, cert, _chain = pkcs12.load_key_and_certificates(data, pwd)
    if cert is None:
        raise ValueError("PKCS#12 sin certificado legible")
    return cert


def _load_certificate_from_pem(path: str) -> x509.Certificate:
    data = Path(path).read_bytes()
    try:
        return x509.load_pem_x509_certificate(data)
    except ValueError:
        return x509.load_der_x509_certificate(data)


def _alert_level_for_days(days_remaining: int) -> tuple[str, int | None]:
    if days_remaining < 0:
        return "expired", 0
    if days_remaining <= 7:
        return "critical", 7
    if days_remaining <= 15:
        return "high", 15
    if days_remaining <= 30:
        return "warning", 30
    return "ok", None


def inspect_mtls_certificate_expiry(
    *,
    source: str,
    cert_path: str | None = None,
    key_path: str | None = None,
    p12_path: str | None = None,
    p12_password: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Inspecta la caducidad del certificado cliente mTLS sin exponer secretos.

    Devuelve ``ok=False`` cuando el certificado ya ha caducado o entra en una
    ventana de alerta 30/15/7 dias.
    """
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    selected_path = (p12_path or cert_path or "").strip()
    cert_type = "p12" if p12_path else "pem"
    if not selected_path:
        return {
            "ok": False,
            "source": source,
            "detail": "mtls_certificate_path_missing",
            "alert_level": "missing",
            "threshold_days": 0,
        }
    key_path_clean = (key_path or "").strip()
    if cert_type == "pem" and not key_path_clean:
        return {
            "ok": False,
            "source": source,
            "detail": "mtls_certificate_key_path_missing",
            "path_name": Path(selected_path).name,
            "type": cert_type,
            "alert_level": "missing",
            "threshold_days": 0,
        }
    if not os.path.isfile(selected_path):
        return {
            "ok": False,
            "source": source,
            "detail": "mtls_certificate_file_missing",
            "path_name": Path(selected_path).name,
            "type": cert_type,
            "alert_level": "missing",
            "threshold_days": 0,
        }
    if cert_type == "pem" and not os.path.isfile(key_path_clean):
        return {
            "ok": False,
            "source": source,
            "detail": "mtls_certificate_key_file_missing",
            "path_name": Path(selected_path).name,
            "key_path_name": Path(key_path_clean).name if key_path_clean else None,
            "type": cert_type,
            "alert_level": "missing",
            "threshold_days": 0,
        }

    try:
        cert = (
            _load_certificate_from_p12(selected_path, p12_password)
            if p12_path
            else _load_certificate_from_pem(selected_path)
        )
        expires_at = _certificate_not_after_utc(cert)
    except Exception as exc:
        return {
            "ok": False,
            "source": source,
            "detail": f"mtls_certificate_read_error:{type(exc).__name__}",
            "path_name": Path(selected_path).name,
            "type": cert_type,
            "alert_level": "read_error",
            "threshold_days": 0,
        }

    seconds_remaining = (expires_at - now_utc).total_seconds()
    days_remaining = math.floor(seconds_remaining / 86400)
    level, threshold = _alert_level_for_days(days_remaining)
    return {
        "ok": level == "ok",
        "source": source,
        "detail": "mtls_certificate_expiry_ok"
        if level == "ok"
        else "mtls_certificate_expiry_alert",
        "path_name": Path(selected_path).name,
        "type": cert_type,
        "subject_cn": _certificate_common_name(cert),
        "expires_at": expires_at.isoformat(),
        "days_remaining": days_remaining,
        "alert_level": level,
        "threshold_days": threshold,
    }


def _global_certificate_config(settings: Settings) -> dict[str, str | None] | None:
    cert_path = (getattr(settings, "AEAT_CLIENT_CERT_PATH", None) or "").strip() or None
    key_path = (getattr(settings, "AEAT_CLIENT_KEY_PATH", None) or "").strip() or None
    p12_path = (getattr(settings, "AEAT_CLIENT_P12_PATH", None) or "").strip() or None
    if not cert_path and not p12_path:
        return None
    return {
        "source": "settings:AEAT_CLIENT_*",
        "cert_path": cert_path,
        "key_path": key_path,
        "p12_path": p12_path,
        "p12_password": getattr(settings, "AEAT_CLIENT_P12_PASSWORD", None),
    }


async def _empresa_certificate_configs(
    db: Any, *, p12_password: str | None
) -> list[dict[str, str | None]]:
    try:
        query = (
            db.table("empresas")
            .select("id,nif,aeat_client_cert_path,aeat_client_key_path,aeat_client_p12_path")
            .limit(500)
        )
        result = await db.execute(query)
    except Exception:
        return []

    rows = (getattr(result, "data", None) or []) if result is not None else []
    configs: list[dict[str, str | None]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        cert_path = str(row.get("aeat_client_cert_path") or "").strip() or None
        key_path = str(row.get("aeat_client_key_path") or "").strip() or None
        p12_path = str(row.get("aeat_client_p12_path") or "").strip() or None
        if not cert_path and not p12_path:
            continue
        empresa_id = str(row.get("id") or "").strip() or "unknown"
        nif = str(row.get("nif") or "").strip()
        label = f"empresa:{empresa_id}"
        if nif:
            label = f"{label}:{nif}"
        configs.append(
            {
                "source": label,
                "cert_path": cert_path,
                "key_path": key_path,
                "p12_path": p12_path,
                "p12_password": p12_password,
            }
        )
    return configs


async def check_aeat_mtls_certificate_expiry(db: Any | None = None) -> dict[str, Any]:
    settings = get_settings()
    configs: list[dict[str, str | None]] = []
    global_config = _global_certificate_config(settings)
    if global_config:
        configs.append(global_config)
    if db is not None:
        configs.extend(
            await _empresa_certificate_configs(db, p12_password=settings.AEAT_CLIENT_P12_PASSWORD)
        )

    if not configs:
        if settings.AEAT_VERIFACTU_ENABLED:
            return {
                "ok": False,
                "detail": "AEAT_VERIFACTU_ENABLED sin certificado mTLS configurado",
                "skipped": False,
                "alert_thresholds_days": list(CERT_EXPIRY_ALERT_THRESHOLDS_DAYS),
                "certificates": [],
            }
        return {
            "ok": True,
            "detail": "AEAT VeriFactu/mTLS not configured",
            "skipped": True,
            "alert_thresholds_days": list(CERT_EXPIRY_ALERT_THRESHOLDS_DAYS),
            "certificates": [],
        }

    certificates = [
        inspect_mtls_certificate_expiry(
            source=str(config.get("source") or "unknown"),
            cert_path=config.get("cert_path"),
            key_path=config.get("key_path"),
            p12_path=config.get("p12_path"),
            p12_password=config.get("p12_password"),
        )
        for config in configs
    ]
    failing = [cert for cert in certificates if not cert.get("ok")]
    body = {
        "ok": not failing,
        "detail": "aeat_mtls_certificates_ok"
        if not failing
        else f"aeat_mtls_certificate_alerts:{len(failing)}",
        "skipped": False,
        "alert_thresholds_days": list(CERT_EXPIRY_ALERT_THRESHOLDS_DAYS),
        "certificates_scanned": len(certificates),
        "certificates": certificates[:_MAX_CERTIFICATES_IN_HEALTH],
    }
    await maybe_send_mtls_certificate_expiry_alert(body)
    return body


async def maybe_send_mtls_certificate_expiry_alert(check: Mapping[str, Any]) -> None:
    if check.get("ok") or check.get("skipped"):
        return
    webhook_url = (
        os.getenv("MTLS_CERT_EXPIRY_ALERT_WEBHOOK_URL")
        or os.getenv("ALERT_WEBHOOK_URL")
        or os.getenv("DISCORD_WEBHOOK_URL")
        or ""
    ).strip()
    if not webhook_url:
        return

    certificates = check.get("certificates")
    if not isinstance(certificates, list):
        return
    alert_items = [cert for cert in certificates if isinstance(cert, Mapping) and not cert.get("ok")]
    if not alert_items:
        return

    now = time.time()
    lines = ["CERT-001 alerta caducidad certificado mTLS"]
    for cert in alert_items[:10]:
        source = str(cert.get("source") or "unknown")
        level = str(cert.get("alert_level") or "unknown")
        threshold = cert.get("threshold_days")
        key = f"{source}:{level}:{threshold}"
        last = _last_alert_sent_by_key.get(key) or 0.0
        if now - last < _ALERT_THROTTLE_SECONDS:
            continue
        _last_alert_sent_by_key[key] = now
        expires_at = cert.get("expires_at") or "n/a"
        days_remaining = cert.get("days_remaining")
        if days_remaining is None:
            days_remaining = "n/a"
        lines.append(
            "- {source} level={level} threshold={threshold}d "
            "expires_at={expires_at} days_remaining={days_remaining}".format(
                source=source,
                level=level,
                threshold=threshold,
                expires_at=expires_at,
                days_remaining=days_remaining,
            )
        )
    if len(lines) == 1:
        return

    payload = {"text": "\n".join(lines), "content": "\n".join(lines)}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            await client.post(webhook_url, json=payload)
    except Exception:
        return
