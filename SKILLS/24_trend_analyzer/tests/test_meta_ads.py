"""Phase 2b-2 tests — Meta Ads Library parser + fetch flow (Playwright stubbed)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from trend_analyzer.cost_tracker import CostTracker  # type: ignore[import-not-found]
from trend_analyzer.providers import meta_ads  # type: ignore[import-not-found]

FIXTURES = Path(__file__).parent / "fixtures"
HTML = (FIXTURES / "meta_ads_library.html").read_text()


class _InMemoryCache:
    def __init__(self):
        self.store: dict[tuple[str, str], object] = {}

    async def get(self, provider, payload):
        return self.store.get((provider, str(payload)))

    async def set(self, provider, payload, value):
        self.store[(provider, str(payload))] = value

    async def get_stale(self, provider, payload):
        return self.store.get((provider, str(payload)))


@pytest.fixture(autouse=True)
def _patch_cache(monkeypatch):
    from trend_analyzer import cache as cache_mod  # type: ignore[import-not-found]
    fake = _InMemoryCache()
    monkeypatch.setattr(meta_ads, "cache", fake)
    monkeypatch.setattr(cache_mod, "get", fake.get)
    monkeypatch.setattr(cache_mod, "set", fake.set)
    monkeypatch.setattr(cache_mod, "get_stale", fake.get_stale)
    return fake


def test_parse_basic_shape():
    signal = meta_ads.parse_library_html(HTML)
    assert signal.active_ads_30d > 0
    # earliest ad in the fixture is 2026-02-02; must be present
    assert signal.earliest_ad_date == date(2026, 2, 2)
    assert "Breakfast Gadgets Co." in signal.top_advertisers
    # the "See ad details" filter must work
    assert "See ad details" not in signal.top_advertisers
    # media distribution buckets
    assert signal.media_distribution["image"] >= 4
    assert signal.media_distribution["video"] >= 1


def test_parse_active_count():
    assert meta_ads._extract_active_count("~152 results for stuff") == 152
    assert meta_ads._extract_active_count("nothing here") == 0


def test_parse_start_dates_filters_future_beyond_day():
    tomorrow_plus_1 = date.today() + timedelta(days=3)
    raw = f"Started running on {tomorrow_plus_1.strftime('%b %d, %Y')}"
    assert meta_ads._extract_start_dates(raw) == []


@pytest.mark.asyncio
async def test_fetch_happy_path(monkeypatch):
    async def fake_fetch_html(url, **kw):
        return HTML

    monkeypatch.setattr(meta_ads._browser, "fetch_html", fake_fetch_html)
    # skip the 30s rate-limit sleep
    async def _no_sleep():
        return None
    monkeypatch.setattr(meta_ads, "_respect_rate_limit", _no_sleep)

    cost = CostTracker(cap_usd=1.0)
    signal = await meta_ads.fetch("mini waffle maker", cost, no_cache=True)

    assert signal.active_ads_30d > 0
    assert signal.top_advertisers
    assert any(
        e.provider == "meta_ads" and e.usd == 0.0
        for e in cost.snapshot().entries
    )


@pytest.mark.asyncio
async def test_fetch_upstream_failure_returns_empty_signal(monkeypatch):
    async def boom(*a, **kw):
        raise RuntimeError("playwright crashed")

    monkeypatch.setattr(meta_ads._browser, "fetch_html", boom)
    async def _no_sleep():
        return None
    monkeypatch.setattr(meta_ads, "_respect_rate_limit", _no_sleep)

    cost = CostTracker(cap_usd=1.0)
    signal = await meta_ads.fetch("busted-kw", cost, no_cache=True)
    assert signal.active_ads_30d == 0
    assert signal.top_advertisers == []
