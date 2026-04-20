"""Seasonality detection."""

from __future__ import annotations

from datetime import date

from trend_analyzer.analysis import seasonality  # type: ignore[import-not-found]
from trend_analyzer.schemas import InterestPoint  # type: ignore[import-not-found]


def _series(values_by_month: dict[int, int]) -> list[InterestPoint]:
    # Build two years of monthly points (YYYY-MM-15).
    pts = []
    for year in (2025, 2026):
        for m, v in values_by_month.items():
            pts.append(InterestPoint(date=date(year, m, 15), value=v))
    return pts


def test_detects_november_december_peak():
    baseline = {m: 40 for m in range(1, 13)}
    baseline[11] = 90
    baseline[12] = 95
    info = seasonality.detect(_series(baseline))
    assert set(info.peak_months) == {"Nov", "Dec"}


def test_detects_february_april_valley():
    baseline = {m: 70 for m in range(1, 13)}
    baseline[2] = 20
    baseline[3] = 22
    baseline[4] = 25
    info = seasonality.detect(_series(baseline))
    assert "Feb" in info.valley_months


def test_not_enough_data_returns_empty():
    info = seasonality.detect(
        [InterestPoint(date=date(2026, 1, 1), value=50)]
    )
    assert info.peak_months == []
    assert "Not enough" in info.summary
