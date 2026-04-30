from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import advisor_service as adv
from app.services.advisor_service import _advisor_tools, _execute_advisor_tool


def test_advisor_tools_registry_contains_expected_names() -> None:
    names = {
        str(t.get("function", {}).get("name") or "")
        for t in _advisor_tools()
        if isinstance(t, dict)
    }
    assert "get_financial_kpis" in names
    assert "get_esg_kpis" in names
    assert "get_bi_liquidity_kpis" in names
    assert "list_cip_vampires" in names


def test_execute_bi_liquidity_tool_respects_top_n_limit() -> None:
    ctx = {
        "bi_intelligence": {
            "dashboard_summary": {"dso_days": 42.0},
            "clientes_presion_cobro": [{"cliente_id": f"c{i}"} for i in range(20)],
        }
    }
    out = _execute_advisor_tool(name="get_bi_liquidity_kpis", args={"top_n": 99}, context=ctx)
    top = out.get("clientes_presion_cobro_top")
    assert isinstance(top, list)
    assert len(top) == 15
    assert out.get("dashboard_summary", {}).get("dso_days") == 42.0


def test_execute_unknown_tool_is_rejected() -> None:
    out = _execute_advisor_tool(name="drop_all_tables", args={}, context={})
    assert str(out.get("error") or "").startswith("tool_not_allowed:")


@pytest.mark.asyncio
async def test_resolve_tool_calls_enriches_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    async def fake_acompletion(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="consultando kpis",
                            tool_calls=[
                                {
                                    "id": "tc_1",
                                    "type": "function",
                                    "function": {"name": "get_financial_kpis", "arguments": "{}"},
                                }
                            ],
                        )
                    )
                ],
                usage={"input_tokens": 10, "output_tokens": 5},
            )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="respuesta final", tool_calls=[]))],
            usage={"input_tokens": 12, "output_tokens": 7},
        )

    monkeypatch.setattr(adv.litellm, "acompletion", fake_acompletion)
    base = [{"role": "user", "content": "dame ebitda"}]
    work_messages, response = await adv._resolve_tool_calls_for_messages(
        model="openai/gpt-4o",
        api_key="dummy",
        base_messages=base,
        context={"ebitda_snapshot": {"ebitda_aprox_sin_iva_eur": 100.0}},
        max_rounds=3,
    )

    assert calls["n"] == 2
    assert response is not None
    tool_msgs = [m for m in work_messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].get("tool_call_id") == "tc_1"

