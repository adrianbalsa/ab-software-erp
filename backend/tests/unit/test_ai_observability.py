from __future__ import annotations

from app.core.ai_observability import compact_ai_usage


def test_compact_ai_usage_from_dict() -> None:
    u = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "ignored": "x"}
    assert compact_ai_usage(u) == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


def test_compact_ai_usage_from_object() -> None:
    class U:
        prompt_tokens = 3
        completion_tokens = 7
        total_tokens = 10

    assert compact_ai_usage(U()) == {"prompt_tokens": 3, "completion_tokens": 7, "total_tokens": 10}
