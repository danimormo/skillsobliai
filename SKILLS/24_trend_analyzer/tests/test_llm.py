"""Phase 2a tests — LLM helper (cost tracking + JSON extraction)."""

from __future__ import annotations

import pytest

from trend_analyzer.cost_tracker import CostTracker  # type: ignore[import-not-found]
from trend_analyzer.llm import _extract_json, call_haiku_json  # type: ignore[import-not-found]

from ._stubs import install_fake_anthropic


def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    raw = "Here you go:\n```json\n{\"a\": 2}\n```\nCheers!"
    assert _extract_json(raw) == {"a": 2}


def test_extract_json_prose_wrapped():
    raw = "Sure, the answer is {\"a\": 3} as above."
    assert _extract_json(raw) == {"a": 3}


def test_extract_json_empty_raises():
    with pytest.raises(ValueError):
        _extract_json("")


@pytest.mark.asyncio
async def test_call_haiku_json_records_cost(monkeypatch):
    install_fake_anthropic(monkeypatch, payload={"primary_keyword": "waffle maker"})
    cost = CostTracker(cap_usd=1.0)

    out = await call_haiku_json(
        system="sys",
        user="u",
        cost=cost,
        operation="normalize_text",
    )

    assert out == {"primary_keyword": "waffle maker"}
    snap = cost.snapshot()
    assert len(snap.entries) == 1
    assert snap.entries[0].provider == "anthropic"
    assert snap.total_usd > 0
