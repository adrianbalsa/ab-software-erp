from __future__ import annotations

from typing import Any


def compact_ai_usage(usage: Any) -> dict[str, Any]:
    """
    Normaliza ``usage`` de LiteLLM/OpenAI/Gemini a un dict pequeño para Sentry (tokens).
    """
    if usage is None:
        return {}
    out: dict[str, Any] = {}
    if isinstance(usage, dict):
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            v = usage.get(k)
            if v is not None:
                out[k] = v
        return out
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        v = getattr(usage, k, None)
        if v is not None:
            out[k] = v
    return out


def attach_ai_usage_to_span(
    span: Any,
    usage: Any,
    *,
    model_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Adjunta tokens y metadatos al span activo (Sentry SDK 2.x)."""
    if span is None:
        return
    payload = compact_ai_usage(usage)
    if model_id:
        payload["model"] = model_id
    if extra:
        for k, v in extra.items():
            if v is not None:
                payload[k] = v
    if not payload:
        return
    try:
        span.set_data("ai.usage", payload)
    except Exception:
        pass
