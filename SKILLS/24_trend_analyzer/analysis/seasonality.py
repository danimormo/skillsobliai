"""Detect seasonal peaks / valleys from a 12-month interest-over-time series."""

from __future__ import annotations

from collections import defaultdict

from ..schemas import InterestPoint, SeasonalityInfo

_MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def detect(points: list[InterestPoint]) -> SeasonalityInfo:
    if len(points) < 6:
        return SeasonalityInfo(summary="Not enough data for seasonality detection.")

    monthly: dict[int, list[int]] = defaultdict(list)
    for p in points:
        monthly[p.date.month].append(p.value)

    month_avg: dict[int, float] = {
        m: sum(vals) / len(vals) for m, vals in monthly.items()
    }
    if not month_avg:
        return SeasonalityInfo()

    overall = sum(month_avg.values()) / len(month_avg)
    peak_threshold = overall + 0.20 * overall
    valley_threshold = overall - 0.20 * overall

    peaks = [m for m, v in month_avg.items() if v >= peak_threshold]
    valleys = [m for m, v in month_avg.items() if v <= valley_threshold]

    peak_names = [_MONTH_NAMES[m - 1] for m in sorted(peaks)]
    valley_names = [_MONTH_NAMES[m - 1] for m in sorted(valleys)]

    summary_parts = []
    if peak_names:
        summary_parts.append(f"peaks in {', '.join(peak_names)}")
    if valley_names:
        summary_parts.append(f"valleys in {', '.join(valley_names)}")
    summary = "; ".join(summary_parts) if summary_parts else "No strong seasonality."

    return SeasonalityInfo(
        peak_months=peak_names,
        valley_months=valley_names,
        summary=summary,
    )
