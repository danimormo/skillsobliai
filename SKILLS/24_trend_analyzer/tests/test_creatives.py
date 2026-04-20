"""Creative-angles + hook-copy generator."""

from __future__ import annotations

import pytest

from trend_analyzer.cost_tracker import CostTracker  # type: ignore[import-not-found]
from trend_analyzer.generate import creatives  # type: ignore[import-not-found]
from trend_analyzer.schemas import (  # type: ignore[import-not-found]
    MetaAdsSignal,
    ProductFingerprint,
    TrendsSignal,
)

from ._stubs import install_fake_anthropic


FP = ProductFingerprint(
    primary_keyword="mini waffle maker",
    secondary_keywords=["breakfast gadget"],
    category="kitchen",
    product_attributes=["compact", "pink", "non-stick"],
    source_kind="text",
    raw_input="mini waffle maker",
)


LLM_RESPONSE = {
    "angles": [
        {
            "name": f"Angle {i}",
            "description": f"Positioning {i}",
            "target_emotion": "joy",
            "format_hint": "UGC",
        }
        for i in range(5)
    ],
    "hooks": [
        {"text": f"Hook {i}", "style": "problem-agitate"} for i in range(5)
    ],
}


@pytest.mark.asyncio
async def test_generate_happy(monkeypatch):
    install_fake_anthropic(monkeypatch, payload=LLM_RESPONSE)
    cost = CostTracker(cap_usd=1.0)
    block = await creatives.generate(FP, TrendsSignal(), MetaAdsSignal(), cost)
    assert len(block.angles) == 5
    assert len(block.hooks) == 5
    assert block.angles[0].name == "Angle 0"


@pytest.mark.asyncio
async def test_generate_handles_string_hooks(monkeypatch):
    install_fake_anthropic(
        monkeypatch,
        payload={
            "angles": LLM_RESPONSE["angles"][:3],
            "hooks": ["Only a string hook", "Another one"],
        },
    )
    cost = CostTracker(cap_usd=1.0)
    block = await creatives.generate(FP, TrendsSignal(), MetaAdsSignal(), cost)
    assert len(block.angles) == 3
    assert len(block.hooks) == 2


@pytest.mark.asyncio
async def test_generate_handles_partial_payload(monkeypatch):
    install_fake_anthropic(monkeypatch, payload={"angles": [], "hooks": []})
    cost = CostTracker(cap_usd=1.0)
    block = await creatives.generate(FP, TrendsSignal(), MetaAdsSignal(), cost)
    assert block.angles == []
    assert block.hooks == []
