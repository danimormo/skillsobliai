"""Phase 2b-3 tests — TikTok Creative Center provider."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trend_analyzer.cost_tracker import CostTracker  # type: ignore[import-not-found]
from trend_analyzer.providers import tiktok  # type: ignore[import-not-found]

from ._stubs import FakeHTTPResponse, install_fake_httpx


FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "tiktok_cc.json").read_text())


class _InMemoryCache:
    def __init__(self):
        self.store: dict = {}
    async def get(self, p, k): return self.store.get((p, str(k)))
    async def set(self, p, k, v): self.store[(p, str(k))] = v
    async def get_stale(self, p, k): return self.store.get((p, str(k)))


@pytest.fixture(autouse=True)
def _patch_cache(monkeypatch):
    from trend_analyzer import cache as cache_mod  # type: ignore[import-not-found]
    fake = _InMemoryCache()
    monkeypatch.setattr(tiktok, "cache", fake)
    monkeypatch.setattr(cache_mod, "get", fake.get)
    monkeypatch.setattr(cache_mod, "set", fake.set)
    monkeypatch.setattr(cache_mod, "get_stale", fake.get_stale)
    return fake


def test_parse_response_happy():
    signal = tiktok.parse_response(FIXTURE, "mini waffle maker")
    # matching hashtag only — "miniwafflemaker" matches
    assert signal.product_mentions >= 1
    assert signal.hashtag_score is not None
    assert signal.hashtag_score > 0


def test_parse_response_unknown_keyword():
    signal = tiktok.parse_response(FIXTURE, "zzzzzz-unknown")
    # fallback: no matches → uses whole list for stats, mentions=3
    assert signal.product_mentions == 3


def test_parse_response_garbage():
    assert tiktok.parse_response({"code": 500, "data": None}, "x").product_mentions == 0
    assert tiktok.parse_response(None, "x").hashtag_score is None


@pytest.mark.asyncio
async def test_fetch_happy(monkeypatch):
    class _Resp:
        status_code = 200
        def json(self): return FIXTURE

    class _Client:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, **kw): return _Resp()

    monkeypatch.setattr(tiktok.httpx, "AsyncClient", _Client)

    cost = CostTracker(cap_usd=1.0)
    signal = await tiktok.fetch("mini waffle maker", cost, no_cache=True)
    assert signal.product_mentions >= 1


@pytest.mark.asyncio
async def test_fetch_http_error(monkeypatch):
    class _Resp:
        status_code = 500
        def json(self): return {}

    class _Client:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, **kw): return _Resp()

    monkeypatch.setattr(tiktok.httpx, "AsyncClient", _Client)
    cost = CostTracker(cap_usd=1.0)
    signal = await tiktok.fetch("x", cost, no_cache=True)
    assert signal.product_mentions == 0
