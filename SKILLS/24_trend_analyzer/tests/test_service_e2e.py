"""End-to-end service test — every upstream is mocked."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from core.skill_interface import SkillContext
from trend_analyzer import service  # type: ignore[import-not-found]
from trend_analyzer.schemas import (  # type: ignore[import-not-found]
    CompetitorStore,
    InterestPoint,
    MetaAdsSignal,
    SaturationSignal,
    TikTokSignal,
    TrendAnalyzerInput,
    TrendsSignal,
)

from ._stubs import install_fake_anthropic


class _InMemoryCache:
    def __init__(self): self.store = {}
    async def get(self, p, k): return self.store.get((p, str(k)))
    async def set(self, p, k, v): self.store[(p, str(k))] = v
    async def get_stale(self, p, k): return self.store.get((p, str(k)))


@pytest.fixture(autouse=True)
def _patch_cache(monkeypatch):
    from trend_analyzer import cache as cache_mod  # type: ignore[import-not-found]
    fake = _InMemoryCache()
    monkeypatch.setattr(service, "cache", fake)
    monkeypatch.setattr(cache_mod, "get", fake.get)
    monkeypatch.setattr(cache_mod, "set", fake.set)
    monkeypatch.setattr(cache_mod, "get_stale", fake.get_stale)
    return fake


def _rising_iot() -> list[InterestPoint]:
    base = date(2026, 1, 1)
    return [
        InterestPoint(date=base + timedelta(weeks=i), value=min(100, 30 + i * 3))
        for i in range(20)
    ]


@pytest.mark.asyncio
async def test_service_runs_end_to_end(monkeypatch):
    # ── normalize_text → uses LLM stub ──────────────────────────────────
    install_fake_anthropic(
        monkeypatch,
        payload={
            "primary_keyword": "mini waffle maker",
            "secondary_keywords": ["waffle"],
            "category": "kitchen",
            "estimated_retail_price_usd": 24.99,
            "product_attributes": ["compact"],
        },
    )

    # ── every provider mocked to return predetermined signals ──────────
    async def fake_trends(kw, cost, **kw2):
        return TrendsSignal(
            interest_over_time=_rising_iot(),
            geography=[],
            related_queries_rising=["mini waffle"],
        )

    async def fake_meta(kw, cost, **kw2):
        return MetaAdsSignal(active_ads_30d=40, active_ads_7d=10, top_advertisers=["X"])

    async def fake_tiktok(kw, cost, **kw2):
        return TikTokSignal(hashtag_score=45.0, product_mentions=3)

    async def fake_shopify(kw, cost, **kw2):
        return SaturationSignal(
            stores_found=8,
            top_competitors=[CompetitorStore(domain="a.com", price_usd=19.99)],
        )

    async def fake_ali(kw, cost, **kw2):
        return 7.0

    async def fake_gs(kw, cost, **kw2):
        return 22.0, (18.0, 30.0)

    monkeypatch.setattr(service.google_trends, "fetch", fake_trends)
    monkeypatch.setattr(service.meta_ads, "fetch", fake_meta)
    monkeypatch.setattr(service.tiktok, "fetch", fake_tiktok)
    monkeypatch.setattr(service.shopify_saturation, "fetch", fake_shopify)
    monkeypatch.setattr(service.aliexpress, "fetch", fake_ali)
    monkeypatch.setattr(service.google_shopping, "fetch", fake_gs)

    skill = service.TrendAnalyzerSkill()
    result = await skill.run(
        TrendAnalyzerInput(text="mini waffle maker"),
        SkillContext(user_id="tester"),
    )
    assert result.success is True
    data = result.data
    assert data is not None
    report = data.report

    assert report.fingerprint.primary_keyword == "mini waffle maker"
    assert 0 <= report.score <= 100
    assert report.verdict in {"GO", "WAIT", "AVOID"}
    assert len(report.sub_scores) == 5
    # Margin = (22 - 7) / 22 * 100 ≈ 68%
    assert report.price.gross_margin_pct is not None
    assert report.price.gross_margin_pct > 60
    # Cost tracker ran
    assert report.cost.total_usd >= 0
    # Markdown was rendered
    assert "Trend Report" in data.markdown
