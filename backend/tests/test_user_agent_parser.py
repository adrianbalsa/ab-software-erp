from __future__ import annotations

from app.core.user_agent_parser import humanize_user_agent, is_mobile_user_agent


def test_humanize_chrome_windows() -> None:
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    assert "Chrome" in humanize_user_agent(ua)
    assert "Windows" in humanize_user_agent(ua)


def test_mobile_detection() -> None:
    assert is_mobile_user_agent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)")
    assert not is_mobile_user_agent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
    )
