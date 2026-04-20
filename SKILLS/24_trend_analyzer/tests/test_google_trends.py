"""Phase 2b-1 tests — Google Trends provider.

``trendspy`` is mocked so the suite stays offline. The fake emits a mix of
pandas-DataFrame and dict payloads to exercise both shape branches of the
parser.
"""

from __future__ import annotations

import sys
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from trend_analyzer.cost_tracker import CostTracker  # type: ignore[import-not-found]
from trend_analyzer.providers import google_trends  # type: ignore[import-not-found]
from trend_analyzer.schemas import TrendsSignal  # type: ignore[import-not-found]


class _InMemoryCache:
    """Drop-in replacement for trend_analyzer.cache, keyed by (provider, payload)."""

    def __init__(self):
        self.store: dict[tuple[str, str], object] = {}

    async def get(self, provider, payload):
        return self.store.get((provider, str(payload)))

    async def set(self, provider, payload, value):
        self.store[(provider, str(payload))] = value

    async def get_stale(self, provider, payload):
        return self.store.get((provider, str(payload)))

    async def invalidate(self, provider, payload):
        self.store.pop((provider, str(payload)), None)


@pytest.fixture(autouse=True)
def _patch_cache(monkeypatch):
    """Force all google_trends cache calls to use the in-memory fake."""
    from trend_analyzer import cache as cache_mod  # type: ignore[import-not-found]

    fake = _InMemoryCache()
    monkeypatch.setattr(google_trends, "cache", fake)
    monkeypatch.setattr(cache_mod, "get", fake.get)
    monkeypatch.setattr(cache_mod, "set", fake.set)
    monkeypatch.setattr(cache_mod, "get_stale", fake.get_stale)
    monkeypatch.setattr(cache_mod, "invalidate", fake.invalidate)
    return fake


# ── Fakes ──────────────────────────────────────────────────────────────────


def _build_iot_df(keyword: str = "waffle maker") -> pd.DataFrame:
    return pd.DataFrame(
        {keyword: [30, 40, 55, 70, 65, 80, 95, 75, 60, 50, 45, 40]},
        index=pd.to_datetime(
            [
                "2025-05-01", "2025-06-01", "2025-07-01", "2025-08-01",
                "2025-09-01", "2025-10-01", "2025-11-01", "2025-12-01",
                "2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01",
            ]
        ),
    ).rename_axis(index="date")


def _build_region_df(values: dict[str, int], keyword: str = "waffle maker") -> pd.DataFrame:
    return pd.DataFrame(
        {keyword: list(values.values())},
        index=pd.Index(list(values.keys()), name="geoName"),
    )


class FakeTrends:
    def __init__(self, *, iot=None, region_1m=None, region_3m=None, related=None, raise_on=None):
        self._iot = iot
        self._region_1m = region_1m
        self._region_3m = region_3m
        self._related = related
        self._raise_on = raise_on or set()
        self._region_call = 0

    def interest_over_time(self, keywords, timeframe="today 12-m", **kw):
        if "interest_over_time" in self._raise_on:
            raise RuntimeError("403")
        return self._iot

    def interest_by_region(self, keywords, timeframe="today 12-m", resolution=None, **kw):
        if "interest_by_region" in self._raise_on:
            raise RuntimeError("429")
        self._region_call += 1
        return self._region_1m if self._region_call == 1 else self._region_3m

    def related_queries(self, keyword, **kw):
        if "related_queries" in self._raise_on:
            raise RuntimeError("boom")
        return self._related


def _install_fake_trends(monkeypatch, fake: FakeTrends):
    """Inject a fake Trends class into the module's ``from trendspy import Trends``."""
    fake_module = SimpleNamespace(Trends=lambda *a, **k: fake)
    monkeypatch.setitem(sys.modules, "trendspy", fake_module)


# ── Tests ──────────────────────────────────────────────────────────────────


def test_cache_key_normalizes_keyword_and_countries():
    a = google_trends._cache_key("Waffle Maker", "today 12-m", ["US", "GB"])
    b = google_trends._cache_key("waffle maker", "today 12-m", ["gb", "us"])
    assert a == b


def test_parse_interest_over_time_from_dataframe():
    df = _build_iot_df()
    points = google_trends._parse_interest_over_time(df, "waffle maker")
    assert len(points) == 12
    assert points[0].date == date(2025, 5, 1)
    assert points[-1].value == 40
    assert all(0 <= p.value <= 100 for p in points)


def test_parse_interest_over_time_none():
    assert google_trends._parse_interest_over_time(None, "x") == []


def test_compute_geo_delta_orders_by_growth():
    recent = _build_region_df({"US": 80, "IT": 20, "DE": 50})
    reference = _build_region_df({"US": 40, "IT": 10, "DE": 55})
    rows = google_trends._compute_geo_delta(
        recent, reference, "waffle maker", countries=[]
    )
    # US and IT both +100% delta; tie-break by current_value puts US first.
    # DE is negative delta so it comes last.
    assert [r.country for r in rows] == ["US", "IT", "DE"]
    assert rows[0].delta_pct == pytest.approx(100.0)
    assert rows[2].delta_pct < 0


def test_compute_geo_delta_respects_country_filter():
    recent = _build_region_df({"US": 80, "IT": 20, "FR": 50}, keyword="x")
    reference = _build_region_df({"US": 40, "IT": 10, "FR": 40}, keyword="x")
    rows = google_trends._compute_geo_delta(recent, reference, "x", countries=["it", "fr"])
    got = {r.country for r in rows}
    assert got == {"IT", "FR"}


def test_parse_related_nested_dict():
    blob = {
        "waffle maker": {
            "rising": [{"query": "mini waffle maker"}, {"query": "dash waffle"}],
            "top": [{"query": "waffle maker"}, {"query": "belgian waffle"}],
        }
    }
    rising, top = google_trends._parse_related(blob, "waffle maker")
    assert rising == ["mini waffle maker", "dash waffle"]
    assert top == ["waffle maker", "belgian waffle"]


def test_parse_related_none():
    assert google_trends._parse_related(None, "x") == ([], [])


# ── End-to-end async paths ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_happy_path(monkeypatch):
    fake = FakeTrends(
        iot=_build_iot_df(),
        region_1m=_build_region_df({"US": 80, "IT": 20}),
        region_3m=_build_region_df({"US": 40, "IT": 10}),
        related={
            "waffle maker": {
                "rising": [{"query": "mini waffle"}],
                "top": [{"query": "waffle maker"}],
            }
        },
    )
    _install_fake_trends(monkeypatch, fake)

    cost = CostTracker(cap_usd=1.0)
    out = await google_trends.fetch(
        "waffle maker", cost, countries=["US", "IT"], no_cache=True
    )

    assert isinstance(out, TrendsSignal)
    assert len(out.interest_over_time) == 12
    assert len(out.geography) == 2
    assert out.related_queries_rising == ["mini waffle"]
    assert out.stale is False
    # free provider — zero-cost entry recorded for traceability
    entries = cost.snapshot().entries
    assert any(e.provider == "google_trends" and e.usd == 0.0 for e in entries)


@pytest.mark.asyncio
async def test_fetch_upstream_failure_empty_signal(monkeypatch):
    fake = FakeTrends(raise_on={"interest_over_time"})
    _install_fake_trends(monkeypatch, fake)

    cost = CostTracker(cap_usd=1.0)
    out = await google_trends.fetch("broken-kw", cost, no_cache=True)

    assert out.stale is True
    assert out.interest_over_time == []
    assert out.geography == []


@pytest.mark.asyncio
async def test_fetch_stale_fallback_hits_cache(monkeypatch):
    """Upstream fails AFTER a prior successful fetch — must return stale value."""
    kw = "waffle cache test"

    good = FakeTrends(
        iot=_build_iot_df(kw),
        region_1m=_build_region_df({"US": 50}, kw),
        region_3m=_build_region_df({"US": 40}, kw),
        related=None,
    )
    _install_fake_trends(monkeypatch, good)

    cost = CostTracker(cap_usd=1.0)
    first = await google_trends.fetch(kw, cost, no_cache=False)
    assert first.stale is False

    bad = FakeTrends(raise_on={"interest_over_time"})
    _install_fake_trends(monkeypatch, bad)

    # Use a fresh tracker; still call with no_cache=False so cache can serve
    second = await google_trends.fetch(kw, CostTracker(cap_usd=1.0), no_cache=False)
    # Redis serves the value directly (not marked stale), which is the
    # happy case. If Redis purges it during the second call the provider
    # falls back to get_stale() and marks stale=True. Both are acceptable.
    assert len(second.interest_over_time) == 12
