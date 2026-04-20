"""Phase 1 tests — pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from trend_analyzer.schemas import (  # type: ignore[import-not-found]
    ProductFingerprint,
    SubScore,
    TrendAnalyzerInput,
    TrendReport,
)


def test_fingerprint_minimal():
    fp = ProductFingerprint(primary_keyword="mini waffle maker", source_kind="text")
    assert fp.category == "other"
    assert fp.secondary_keywords == []


def test_fingerprint_rejects_bad_category():
    with pytest.raises(ValidationError):
        ProductFingerprint(
            primary_keyword="x",
            source_kind="text",
            category="not-a-real-category",  # type: ignore[arg-type]
        )


def test_input_accepts_text_only():
    inp = TrendAnalyzerInput(text="led strip rgb")
    assert inp.text == "led strip rgb"
    assert inp.url is None
    assert inp.countries  # defaults populated


def test_sub_score_bounds():
    with pytest.raises(ValidationError):
        SubScore(name="momentum", value=101, weight=0.3, explanation="x")
    with pytest.raises(ValidationError):
        SubScore(name="momentum", value=50, weight=1.5, explanation="x")


def test_trend_report_roundtrip():
    fp = ProductFingerprint(primary_keyword="k", source_kind="text")
    subs = [
        SubScore(name="momentum", value=70, weight=0.3, explanation="a"),
        SubScore(name="saturation", value=60, weight=0.25, explanation="b"),
        SubScore(name="ad_velocity", value=50, weight=0.2, explanation="c"),
        SubScore(name="seasonality", value=40, weight=0.15, explanation="d"),
        SubScore(name="margin", value=80, weight=0.1, explanation="e"),
    ]
    report = TrendReport(
        fingerprint=fp,
        score=62.5,
        verdict="WAIT",
        rationale="sample",
        sub_scores=subs,
    )
    payload = report.model_dump(mode="json")
    assert payload["verdict"] == "WAIT"
    # Round-trip via JSON must succeed
    again = TrendReport.model_validate(payload)
    assert again.score == 62.5
