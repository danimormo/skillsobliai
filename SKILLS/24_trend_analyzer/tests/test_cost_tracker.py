"""Phase 1 tests — cost tracker behavior (no network, no Redis)."""

from __future__ import annotations

import pytest

from trend_analyzer.cost_tracker import (  # type: ignore[import-not-found]
    CostCapExceeded,
    CostTracker,
    tracker,
)


def test_add_accumulates_total():
    t = CostTracker(cap_usd=0.05)
    t.add(provider="a", operation="op1", usd=0.01)
    t.add(provider="b", operation="op2", usd=0.02)
    assert t.total == pytest.approx(0.03)
    assert len(t.snapshot().entries) == 2


def test_cap_exceeded_raises():
    t = CostTracker(cap_usd=0.05)
    t.add(provider="x", operation="big", usd=0.04)
    with pytest.raises(CostCapExceeded) as exc:
        t.add(provider="x", operation="over", usd=0.02)
    assert "Cost cap" in exc.value.message
    assert exc.value.code == "COST_CAP_EXCEEDED"


def test_force_bypasses_cap():
    t = CostTracker(cap_usd=0.05, force=True)
    t.add(provider="x", operation="big", usd=0.04)
    t.add(provider="x", operation="over", usd=0.10)  # would normally raise
    assert t.total == pytest.approx(0.14)
    assert t.snapshot().cap_hit is True


def test_negative_cost_rejected():
    t = CostTracker(cap_usd=0.05)
    with pytest.raises(ValueError):
        t.add(provider="x", operation="bad", usd=-0.01)


def test_claude_haiku_pricing_math():
    t = CostTracker(cap_usd=1.0)
    t.add_claude_haiku(operation="normalize", input_tokens=1000, output_tokens=500)
    # 1000 * $1/MTok + 500 * $5/MTok = 0.001 + 0.0025 = 0.0035
    assert t.total == pytest.approx(0.0035)


def test_context_manager_yields_tracker():
    with tracker(cap_usd=0.05) as t:
        t.add(provider="p", operation="o", usd=0.001)
    assert t.total == pytest.approx(0.001)
