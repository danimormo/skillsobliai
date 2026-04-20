"""Markdown + JSON writers."""

from __future__ import annotations

import json

from trend_analyzer.report.json_out import to_json  # type: ignore[import-not-found]
from trend_analyzer.report.markdown_out import to_markdown  # type: ignore[import-not-found]
from trend_analyzer.schemas import (  # type: ignore[import-not-found]
    CompetitorStore,
    CostBreakdown,
    CostEntry,
    CreativeAngle,
    CreativesBlock,
    HookCopy,
    MetaAdsSignal,
    PriceSignal,
    ProductFingerprint,
    SaturationSignal,
    SeasonalityInfo,
    SubScore,
    TrendReport,
)


def _sample_report() -> TrendReport:
    fp = ProductFingerprint(
        primary_keyword="mini waffle maker",
        secondary_keywords=["waffle", "gadget"],
        category="kitchen",
        estimated_retail_price_usd=24.99,
        product_attributes=["compact", "pink"],
        source_kind="text",
        raw_input="mini waffle maker",
    )
    subs = [
        SubScore(name="momentum", value=80, weight=0.30, explanation="+40%"),
        SubScore(name="saturation", value=70, weight=0.25, explanation="12 stores"),
        SubScore(name="ad_velocity", value=60, weight=0.20, explanation="fresh"),
        SubScore(name="seasonality", value=100, weight=0.15, explanation="peak"),
        SubScore(name="margin", value=90, weight=0.10, explanation="72%"),
    ]
    return TrendReport(
        fingerprint=fp,
        score=76.5,
        verdict="GO",
        rationale="Strong signals.",
        sub_scores=subs,
        seasonality=SeasonalityInfo(peak_months=["Nov", "Dec"], summary="peaks in Nov, Dec"),
        saturation=SaturationSignal(
            stores_found=12,
            top_competitors=[
                CompetitorStore(domain="a.com", price_usd=24.99),
                CompetitorStore(domain="b.com", price_usd=19.99),
            ],
        ),
        meta_ads=MetaAdsSignal(active_ads_30d=40, active_ads_7d=15, top_advertisers=["X", "Y"]),
        price=PriceSignal(
            retail_price_median_usd=25.0,
            retail_price_range_usd=(19.0, 35.0),
            supplier_price_median_usd=7.0,
            gross_margin_pct=72,
        ),
        creatives=CreativesBlock(
            angles=[CreativeAngle(name="Fresh angle", description="desc",
                                  target_emotion="joy", format_hint="UGC")],
            hooks=[HookCopy(text="Quick waffles, zero cleanup")],
        ),
        cost=CostBreakdown(
            total_usd=0.015,
            entries=[CostEntry(provider="anthropic", operation="norm", usd=0.015)],
        ),
        warnings=["Google Trends stale"],
    )


def test_markdown_includes_all_sections():
    md = to_markdown(_sample_report())
    # Key sections
    for header in (
        "# Trend Report",
        "## Sub-scores",
        "## Fingerprint",
        "## Seasonality",
        "## Competition",
        "## Meta Ads Library",
        "## Price & Margin",
        "## Creative Angles",
        "## Hook Copy",
        "## Cost",
        "## Warnings",
    ):
        assert header in md, f"missing header: {header}"
    # Verdict badge + key values
    assert "**GO**" in md
    assert "76.5" in md
    assert "12 stores" in md


def test_json_roundtrips_back_into_report():
    original = _sample_report()
    raw = to_json(original)
    parsed = json.loads(raw)
    from trend_analyzer.schemas import TrendReport  # type: ignore[import-not-found]
    rehydrated = TrendReport.model_validate(parsed)
    assert rehydrated.score == original.score
    assert rehydrated.verdict == original.verdict
    assert len(rehydrated.sub_scores) == 5


def test_markdown_handles_empty_report():
    empty = TrendReport(
        fingerprint=ProductFingerprint(primary_keyword="x", source_kind="text"),
        score=0.0,
        verdict="AVOID",
        rationale="no data",
        sub_scores=[
            SubScore(name="momentum", value=0, weight=0.30, explanation=""),
        ],
    )
    md = to_markdown(empty)
    assert "**AVOID**" in md
    # Optional sections must not appear when their data is empty
    assert "## Competition" not in md
    assert "## Meta Ads Library" not in md
