"""Scoring algorithm — covers all 5 sub-scores + the final verdict rules."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from trend_analyzer.analysis import scoring  # type: ignore[import-not-found]
from trend_analyzer.schemas import (  # type: ignore[import-not-found]
    InterestPoint,
    MetaAdsSignal,
    PriceSignal,
    SaturationSignal,
    SeasonalityInfo,
    SubScore,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


def _rising_iot(weeks: int = 20) -> list[InterestPoint]:
    """Interest climbing steadily week over week."""
    base = date(2026, 1, 1)
    return [
        InterestPoint(date=base + timedelta(weeks=i), value=min(100, 30 + i * 3))
        for i in range(weeks)
    ]


def _declining_iot(weeks: int = 20) -> list[InterestPoint]:
    base = date(2026, 1, 1)
    return [
        InterestPoint(date=base + timedelta(weeks=i), value=max(5, 95 - i * 3))
        for i in range(weeks)
    ]


# ── Sub-score unit tests ──────────────────────────────────────────────────


def test_momentum_rising_gives_high_score():
    s = scoring.score_momentum(_rising_iot())
    assert s.value > 70
    assert "%" in s.explanation


def test_momentum_declining_gives_low_score():
    s = scoring.score_momentum(_declining_iot())
    assert s.value < 30


def test_momentum_empty_is_neutral():
    s = scoring.score_momentum([])
    assert s.value == 50.0


def test_saturation_blue_ocean():
    s = scoring.score_saturation(SaturationSignal(stores_found=0))
    assert s.value == 100.0


def test_saturation_very_saturated():
    s = scoring.score_saturation(SaturationSignal(stores_found=50))
    assert s.value == 0.0


def test_ad_velocity_no_ads_low():
    s = scoring.score_ad_velocity(MetaAdsSignal(active_ads_30d=0, active_ads_7d=0))
    assert s.value == 25.0


def test_ad_velocity_fresh_high():
    s = scoring.score_ad_velocity(MetaAdsSignal(active_ads_30d=20, active_ads_7d=18))
    assert s.value > 80


def test_seasonality_at_peak():
    today = date(2026, 12, 15)
    s = scoring.score_seasonality(
        SeasonalityInfo(peak_months=["Dec"], summary="x"), today=today
    )
    assert s.value == 100.0


def test_seasonality_six_months_away():
    s = scoring.score_seasonality(
        SeasonalityInfo(peak_months=["Dec"], summary="x"),
        today=date(2026, 6, 15),
    )
    assert s.value == 0.0


def test_seasonality_no_data_neutral():
    s = scoring.score_seasonality(SeasonalityInfo())
    assert s.value == 50.0


def test_margin_high():
    s = scoring.score_margin(PriceSignal(gross_margin_pct=70))
    assert s.value == 100.0


def test_margin_low():
    s = scoring.score_margin(PriceSignal(gross_margin_pct=15))
    assert s.value == 0.0


def test_margin_midrange_linear():
    s = scoring.score_margin(PriceSignal(gross_margin_pct=40))
    assert s.value == pytest.approx(50.0, abs=0.5)


def test_margin_unknown_neutral():
    s = scoring.score_margin(PriceSignal())
    assert s.value == 50.0


# ── Aggregate + verdict — 5 scenarios ─────────────────────────────────────


def _sub(name, value, weight):
    return SubScore(name=name, value=value, weight=weight, explanation="")


def test_scenario_blue_ocean_trending_go():
    subs = [
        _sub("momentum", 90, 0.30),
        _sub("saturation", 95, 0.25),
        _sub("ad_velocity", 70, 0.20),
        _sub("seasonality", 80, 0.15),
        _sub("margin", 100, 0.10),
    ]
    total = scoring.aggregate(subs)
    verdict, _ = scoring.decide(total, subs)
    assert total >= 70
    assert verdict == "GO"


def test_scenario_saturated_declining_avoid():
    subs = [
        _sub("momentum", 10, 0.30),
        _sub("saturation", 5, 0.25),
        _sub("ad_velocity", 20, 0.20),
        _sub("seasonality", 30, 0.15),
        _sub("margin", 15, 0.10),
    ]
    total = scoring.aggregate(subs)
    verdict, _ = scoring.decide(total, subs)
    assert total < 50
    assert verdict == "AVOID"


def test_scenario_seasonal_peak_with_moderate_saturation_wait():
    subs = [
        _sub("momentum", 80, 0.30),
        _sub("saturation", 35, 0.25),  # below GO threshold
        _sub("ad_velocity", 85, 0.20),
        _sub("seasonality", 100, 0.15),
        _sub("margin", 70, 0.10),
    ]
    total = scoring.aggregate(subs)
    verdict, _ = scoring.decide(total, subs)
    assert total >= 70
    # High total but saturation below 40 → WAIT
    assert verdict == "WAIT"


def test_scenario_seasonal_valley_wait():
    subs = [
        _sub("momentum", 55, 0.30),
        _sub("saturation", 70, 0.25),
        _sub("ad_velocity", 50, 0.20),
        _sub("seasonality", 10, 0.15),
        _sub("margin", 55, 0.10),
    ]
    total = scoring.aggregate(subs)
    verdict, _ = scoring.decide(total, subs)
    assert 50 <= total < 70
    assert verdict == "WAIT"


def test_scenario_niche_stable_wait():
    subs = [
        _sub("momentum", 50, 0.30),
        _sub("saturation", 75, 0.25),
        _sub("ad_velocity", 50, 0.20),
        _sub("seasonality", 50, 0.15),
        _sub("margin", 60, 0.10),
    ]
    total = scoring.aggregate(subs)
    verdict, _ = scoring.decide(total, subs)
    assert verdict == "WAIT"


def test_aggregate_max_clean_input():
    legal = [_sub("momentum", 100, 1.0)]
    assert scoring.aggregate(legal) == 100.0


def test_aggregate_zero_weight_returns_zero():
    subs = [_sub("momentum", 100, 0.0)]
    assert scoring.aggregate(subs) == 0.0
