"""Tests for the Shopify saturation provider."""

from __future__ import annotations

import pytest

from trend_analyzer.cost_tracker import CostTracker  # type: ignore[import-not-found]
from trend_analyzer.providers import shopify_saturation as ss  # type: ignore[import-not-found]


class _InMemoryCache:
    def __init__(self): self.store = {}
    async def get(self, p, k): return self.store.get((p, str(k)))
    async def set(self, p, k, v): self.store[(p, str(k))] = v
    async def get_stale(self, p, k): return self.store.get((p, str(k)))


@pytest.fixture(autouse=True)
def _patch_cache(monkeypatch):
    from trend_analyzer import cache as cache_mod  # type: ignore[import-not-found]
    fake = _InMemoryCache()
    monkeypatch.setattr(ss, "cache", fake)
    monkeypatch.setattr(cache_mod, "get", fake.get)
    monkeypatch.setattr(cache_mod, "set", fake.set)
    monkeypatch.setattr(cache_mod, "get_stale", fake.get_stale)
    return fake


# ── Matcher / parsers ─────────────────────────────────────────────────────


def test_find_match_by_primary_keyword():
    products = [
        {"title": "Mini Waffle Maker Pink", "handle": "mini-waffle-maker",
         "variants": [{"price": "24.99"}]},
    ]
    match = ss._find_match(products, "mini waffle maker", [], "store.com")
    assert match is not None
    assert match.domain == "store.com"
    assert match.price_usd == 24.99
    assert str(match.product_url) == "https://store.com/products/mini-waffle-maker"


def test_find_match_by_secondary_keyword():
    products = [{"title": "Belgian Breakfast Gadget", "handle": "bbg",
                 "variants": [{"price": "19"}]}]
    match = ss._find_match(products, "mini waffle maker", ["breakfast gadget"], "s.com")
    assert match is not None


def test_find_match_rejects_unrelated():
    products = [{"title": "iPhone Case Silicone", "handle": "case"}]
    assert ss._find_match(products, "mini waffle maker", [], "s.com") is None


# ── End-to-end with mocked httpx + stores ─────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_counts_matches(monkeypatch):
    # Tiny fake store list
    monkeypatch.setattr(ss, "_load_store_list", lambda: ["a.com", "b.com"])

    async def fake_fetch_one(client, domain):
        if domain == "a.com":
            return [{"title": "Mini Waffle Maker Pink", "handle": "mw",
                     "variants": [{"price": "24.99"}]}]
        return [{"title": "Unrelated Item"}]

    monkeypatch.setattr(ss, "_fetch_one", fake_fetch_one)

    cost = CostTracker(cap_usd=1.0)
    signal = await ss.fetch("mini waffle maker", cost, sample_size=2, no_cache=True)
    assert signal.stores_found == 1
    assert signal.top_competitors[0].domain == "a.com"


@pytest.mark.asyncio
async def test_fetch_empty_store_list(monkeypatch):
    monkeypatch.setattr(ss, "_load_store_list", lambda: [])
    cost = CostTracker(cap_usd=1.0)
    signal = await ss.fetch("x", cost, no_cache=True)
    assert signal.stores_found == 0
