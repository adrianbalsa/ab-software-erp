"""
Resumen legible de User-Agent para UI de sesiones [cite: 2026-03-22].
Sin dependencias externas (heurística).
"""

from __future__ import annotations


def is_mobile_user_agent(user_agent: str | None) -> bool:
    if not user_agent or not str(user_agent).strip():
        return False
    ua = user_agent.lower()
    return any(
        x in ua
        for x in (
            "mobile",
            "android",
            "iphone",
            "ipod",
            "ipad",
            "webos",
            "blackberry",
        )
    )


def humanize_user_agent(user_agent: str | None) -> str:
    """
    Ejemplos: ``Chrome en Windows``, ``Safari en iOS``, ``Firefox en Linux``.
    """
    if not user_agent or not str(user_agent).strip():
        return "Navegador desconocido"

    ua = user_agent

    browser = "Navegador"
    ual = ua.lower()
    if "edg/" in ual or "edge/" in ual:
        browser = "Edge"
    elif "opr/" in ual or "opera" in ual:
        browser = "Opera"
    elif "chrome" in ual and "chromium" not in ual:
        browser = "Chrome"
    elif "firefox" in ual:
        browser = "Firefox"
    elif "safari" in ual and "chrome" not in ual:
        browser = "Safari"
    elif "chromium" in ual:
        browser = "Chromium"

    os_name = "desconocido"
    if "windows nt" in ual:
        os_name = "Windows"
    elif "mac os x" in ual or "macintosh" in ual:
        os_name = "macOS"
    elif "iphone" in ual or "ipad" in ual:
        os_name = "iOS"
    elif "android" in ual:
        os_name = "Android"
    elif "linux" in ual:
        os_name = "Linux"

    return f"{browser} en {os_name}"


def truncate_ua(ua: str | None, max_len: int = 512) -> str | None:
    if ua is None:
        return None
    s = str(ua).strip()
    if not s:
        return None
    return s[:max_len]
