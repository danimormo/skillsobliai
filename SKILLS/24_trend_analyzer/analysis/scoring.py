"""Trend Score 0-100 + GO / WAIT / AVOID verdict.

Weights and scoring rules are defined verbatim in SKILL.md. Keep this
module pure — no I/O, no network — so it can be unit-tested with
synthetic sub-score inputs.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

from ..schemas import (
    InterestPoint,
    MetaAdsSignal,
    PriceSignal,
    SaturationSignal,
    SeasonalityInfo,
    SubScore,
    Verdict,
)


WEIGHTS: dict[str, float] = {
    "momentum": 0.30,
    "saturation": 0.25,
    "ad_velocity": 0.20,
    "seasonality": 0.15,
    "margin": 0.10,
}

# Thresholds (per SKILL.md)
GO_MIN_SCORE = 70.0
GO_MIN_SATURATION = 40.0
WAIT_MIN_SCORE = 50.0


# ── Individual sub-score builders ──────────────────────────────────────────


def score_momentum(interest: list[InterestPoint]) -> SubScore:
    """Δ% of last 30d average vs the prior 90d average.

    +50% → 100 pts, -50% → 0 pts, 0% → 50 pts, clipped to [0, 100].
    """
    if not interest or len(interest) < 4:
        return SubScore(
            name="momentum",
            value=50.0,
            weight=WEIGHTS["momentum"],
            explanation="Insufficient Google Trends data — neutral 50 pts assumed.",
        )

    ordered = sorted(interest, key=lambda p: p.date)
    recent = ordered[-4:]
    prior = ordered[-16:-4] if len(ordered) >= 16 else ordered[:-4]

    recent_avg = _avg(p.value for p in recent)
    prior_avg = _avg(p.value for p in prior) or 1.0

    delta_pct = (recent_avg - prior_avg) / prior_avg * 100
    value = max(0.0, min(100.0, 50.0 + delta_pct))  # +50% → 100, -50% → 0

    sign = "+" if delta_pct >= 0 else ""
    return SubScore(
        name="momentum",
        value=round(value, 1),
        weight=WEIGHTS["momentum"],
        explanation=f"{sign}{delta_pct:.0f}% search interest last 30d vs prior 90d",
    )


def score_saturation(sat: SaturationSignal) -> SubScore:
    """100 − min(100, stores × 2). 0 stores → 100 pts (blue ocean)."""
    value = max(0.0, 100.0 - min(100.0, sat.stores_found * 2))
    return SubScore(
        name="saturation",
        value=round(value, 1),
        weight=WEIGHTS["saturation"],
        explanation=f"{sat.stores_found} competing stores identified",
    )


def score_ad_velocity(meta: MetaAdsSignal) -> SubScore:
    """Relative growth of active ads last 7d vs last 30d.

    Fraction of 30-day ads that launched in the last 7 days. 100 pts when
    everything is brand-new, 0 pts when no 30-day activity at all.
    """
    if meta.active_ads_30d <= 0:
        return SubScore(
            name="ad_velocity",
            value=25.0,
            weight=WEIGHTS["ad_velocity"],
            explanation="No Meta ads detected in the last 30 days.",
        )

    fresh_ratio = meta.active_ads_7d / max(meta.active_ads_30d, 1)
    # Expected baseline under uniform launches = 7/30 ≈ 0.23.
    baseline = 7 / 30
    delta = fresh_ratio - baseline
    value = max(0.0, min(100.0, 50.0 + delta * 200))

    return SubScore(
        name="ad_velocity",
        value=round(value, 1),
        weight=WEIGHTS["ad_velocity"],
        explanation=(
            f"{meta.active_ads_7d} of {meta.active_ads_30d} active ads launched in last 7d"
        ),
    )


def score_seasonality(season: SeasonalityInfo, today: date | None = None) -> SubScore:
    """Distance-from-peak score: peak month or 1 month prior = 100, 6 months = 0."""
    if not season.peak_months:
        return SubScore(
            name="seasonality",
            value=50.0,
            weight=WEIGHTS["seasonality"],
            explanation="No clear seasonal pattern detected — neutral 50 pts.",
        )

    today = today or date.today()
    current_month = today.month
    peaks = [_month_to_int(m) for m in season.peak_months if _month_to_int(m)]
    if not peaks:
        return SubScore(
            name="seasonality",
            value=50.0,
            weight=WEIGHTS["seasonality"],
            explanation="Peak months unparsable.",
        )

    # Distance = min forward-distance to any peak, measured in months.
    distances = [((p - current_month) % 12) for p in peaks]
    forward = min(distances)
    backward = min((12 - d) % 12 for d in distances)
    distance = min(forward, backward)

    # Linear: 0 months = 100, 6 months = 0.
    value = max(0.0, 100.0 - (distance * 100 / 6))

    return SubScore(
        name="seasonality",
        value=round(value, 1),
        weight=WEIGHTS["seasonality"],
        explanation=f"Peak month(s): {', '.join(season.peak_months)}; current distance {distance} mo",
    )


def score_margin(price: PriceSignal) -> SubScore:
    """Gross-margin % → >60% = 100 pt, <20% = 0 pt, linear in between."""
    margin = price.gross_margin_pct
    if margin is None:
        return SubScore(
            name="margin",
            value=50.0,
            weight=WEIGHTS["margin"],
            explanation="Supplier or retail price unknown — neutral 50 pts.",
        )

    if margin >= 60:
        value = 100.0
    elif margin <= 20:
        value = 0.0
    else:
        value = (margin - 20) * (100 / 40)

    return SubScore(
        name="margin",
        value=round(value, 1),
        weight=WEIGHTS["margin"],
        explanation=f"Estimated gross margin: {margin:.0f}%",
    )


# ── Aggregation ────────────────────────────────────────────────────────────


def aggregate(sub_scores: list[SubScore]) -> float:
    """Weighted mean, clamped to [0, 100]."""
    weighted = sum(s.value * s.weight for s in sub_scores)
    total_weight = sum(s.weight for s in sub_scores)
    if total_weight <= 0:
        return 0.0
    return round(max(0.0, min(100.0, weighted / total_weight)), 1)


def decide(score: float, sub_scores: list[SubScore]) -> tuple[Verdict, str]:
    saturation = next(
        (s.value for s in sub_scores if s.name == "saturation"), None
    )
    saturation = saturation if saturation is not None else 0.0

    if score >= GO_MIN_SCORE and saturation >= GO_MIN_SATURATION:
        return "GO", f"Strong signals ({score:.0f}/100) with breathing room on saturation."
    if score >= WAIT_MIN_SCORE:
        return "WAIT", f"Mixed signals ({score:.0f}/100) — refine angle before launching."
    return "AVOID", f"Weak signals ({score:.0f}/100) — high risk of unprofitable launch."


# ── Helpers ────────────────────────────────────────────────────────────────


_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _month_to_int(name: str) -> int | None:
    return _MONTHS.get(name.strip().lower())


def _avg(values: Iterable[float]) -> float:
    xs = list(values)
    return sum(xs) / len(xs) if xs else 0.0
