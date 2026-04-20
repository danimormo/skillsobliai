"""Tests for AliExpress + Google Shopping price providers."""

from __future__ import annotations

from pathlib import Path

import pytest

from trend_analyzer.cost_tracker import CostTracker  # type: ignore[import-not-found]
from trend_analyzer.providers import aliexpress, google_shopping  # type: ignore[import-not-found]

FIXTURES = Path(__file__).parent / "fixtures"
ALI_HTML = (FIXTURES / "aliexpress_search.html").read_text()
GS_HTML = (FIXTURES / "google_shopping.html").read_text()


class _InMemoryCache:
    def __init__(self): self.store = {}
    async def get(self, p, k): return self.store.get((p, str(k)))
    async def set(self, p, k, v): self.store[(p, str(k))] = v
    async def get_stale(self, p, k): return self.store.get((p, str(k)))


@pytest.fixture(autouse=True)
def _patch_cache(monkeypatch):
    from trend_analyzer import cache as cache_mod  # type: ignore[import-not-found]
    fake = _InMemoryCache()
    for mod in (aliexpress, google_shopping):
        monkeypatch.setattr(mod, "cache", fake)
    monkeypatch.setattr(cache_mod, "get", fake.get)
    monkeypatch.setattr(cache_mod, "set", fake.set)
    monkeypatch.setattr(cache_mod, "get_stale", fake.get_stale)
    return fake


# ── AliExpress ────────────────────────────────────────────────────────────


def test_ali_parse_median_price():
    median = aliexpress.parse_median_price(ALI_HTML)
    # prices in fixture: 6.50, 7.20, 5.90, 8.00, 6.80, 9.20 → sorted
    # median of 6 = (6.80 + 7.20) / 2 = 7.00
    assert median == pytest.approx(7.00, rel=1e-3)


def test_ali_parse_empty():
    assert aliexpress.parse_median_price("<html></html>") is None


@pytest.mark.asyncio
async def test_ali_fetch_happy(monkeypatch):
    async def fake_fetch_html(url, **kw):
        return ALI_HTML

    monkeypatch.setattr(aliexpress._browser, "fetch_html", fake_fetch_html)
    cost = CostTracker(cap_usd=1.0)
    median = await aliexpress.fetch("mini waffle maker", cost, no_cache=True)
    assert median is not None and median > 0


@pytest.mark.asyncio
async def test_ali_fetch_failure(monkeypatch):
    async def boom(url, **kw):
        raise RuntimeError("blocked")

    monkeypatch.setattr(aliexpress._browser, "fetch_html", boom)
    cost = CostTracker(cap_usd=1.0)
    assert await aliexpress.fetch("x", cost, no_cache=True) is None


# ── Google Shopping ───────────────────────────────────────────────────────


def test_gs_parse_prices():
    median, price_range = google_shopping.parse_prices(GS_HTML)
    assert median is not None
    # prices: 19.99, 24.50, 22.00, 29.95, 34.99 → sorted → 24.50 median
    assert median == pytest.approx(24.50, rel=1e-3)
    assert price_range == (19.99, 34.99)


def test_gs_parse_empty():
    median, rng = google_shopping.parse_prices("<html></html>")
    assert median is None and rng is None


@pytest.mark.asyncio
async def test_gs_fetch_happy(monkeypatch):
    async def fake_fetch_html(url, **kw):
        return GS_HTML

    monkeypatch.setattr(google_shopping._browser, "fetch_html", fake_fetch_html)
    cost = CostTracker(cap_usd=1.0)
    median, rng = await google_shopping.fetch("x", cost, no_cache=True)
    assert median is not None and rng is not None
