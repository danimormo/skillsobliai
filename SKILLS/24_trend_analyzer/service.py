"""Trend Analyzer skill — end-to-end orchestrator.

Flow per request::

    input
      → normalize (text / url / image → ProductFingerprint)
      → tier-1 providers in parallel
          ├─ google_trends      (interest + geography + related queries)
          ├─ meta_ads           (active ads + advertisers)
          ├─ tiktok             (hashtag score)
          ├─ shopify_saturation (competitor stores)
          ├─ aliexpress         (supplier median price)
          └─ google_shopping    (retail median + range)
      → analysis (seasonality from IOT, price/margin, scoring, verdict)
      → creative generation (5 angles + 5 hooks), unless skipped
      → report (JSON + Markdown), cost breakdown, warnings
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from core.config import settings
from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult

from . import cache
from .analysis import scoring, seasonality
from .cost_tracker import CostTracker, tracker
from .generate import creatives as creatives_gen
from .normalize.image import normalize_image
from .normalize.text import normalize_text
from .normalize.url import normalize_url
from .providers import (
    aliexpress,
    google_shopping,
    google_trends,
    meta_ads,
    shopify_saturation,
    tiktok,
)
from .report.markdown_out import to_markdown
from .schemas import (
    CreativesBlock,
    MetaAdsSignal,
    PriceSignal,
    ProductFingerprint,
    SaturationSignal,
    SubScore,
    TikTokSignal,
    TrendAnalyzerInput,
    TrendAnalyzerOutput,
    TrendReport,
    TrendsSignal,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "trend-analyzer"


def _validate_input(inp: TrendAnalyzerInput) -> None:
    provided = [x for x in (inp.text, inp.url, inp.image_url, inp.image_b64) if x]
    if len(provided) == 0:
        raise InvalidParamsError(
            message="Provide one of: text, url, image_url, image_b64.",
            skill=SKILL_NAME,
            code="INVALID_PARAMS",
        )
    if len(provided) > 1:
        raise InvalidParamsError(
            message="Exactly one input modality allowed per call.",
            skill=SKILL_NAME,
            code="INVALID_PARAMS",
        )


async def _resolve_fingerprint(
    inp: TrendAnalyzerInput, cost: CostTracker
) -> ProductFingerprint:
    cache_key = inp.text or str(inp.url) or str(inp.image_url) or "<b64>"

    if not inp.no_cache:
        hit = await cache.get("fingerprint", cache_key)
        if hit is not None:
            try:
                return ProductFingerprint.model_validate(hit)
            except Exception:
                logger.warning("fingerprint cache corrupt for key=%s", cache_key)

    if inp.text:
        fp = await normalize_text(inp.text, cost)
    elif inp.url:
        fp = await normalize_url(str(inp.url), cost)
    else:
        fp = await normalize_image(
            image_url=str(inp.image_url) if inp.image_url else None,
            image_b64=inp.image_b64,
            cost=cost,
        )

    if not inp.no_cache:
        await cache.set("fingerprint", cache_key, fp.model_dump())
    return fp


async def _fetch_all_providers(
    fp: ProductFingerprint,
    inp: TrendAnalyzerInput,
    cost: CostTracker,
    warnings: list[str],
) -> tuple[TrendsSignal, MetaAdsSignal, TikTokSignal, SaturationSignal, float | None, tuple[float | None, tuple[float, float] | None]]:
    """Run every tier-1 provider in parallel; never raise — collect warnings."""
    kw = fp.primary_keyword

    tasks = [
        google_trends.fetch(kw, cost, countries=inp.countries, no_cache=inp.no_cache),
        meta_ads.fetch(kw, cost, no_cache=inp.no_cache),
        tiktok.fetch(kw, cost, no_cache=inp.no_cache),
        shopify_saturation.fetch(
            kw, cost,
            secondary_keywords=fp.secondary_keywords,
            no_cache=inp.no_cache,
        ),
        aliexpress.fetch(kw, cost, no_cache=inp.no_cache),
        google_shopping.fetch(kw, cost, no_cache=inp.no_cache),
    ]

    results: list[Any] = await asyncio.gather(*tasks, return_exceptions=True)
    labels = [
        "google_trends",
        "meta_ads",
        "tiktok",
        "shopify_saturation",
        "aliexpress",
        "google_shopping",
    ]
    empties: dict[str, Any] = {
        "google_trends": TrendsSignal(stale=True),
        "meta_ads": MetaAdsSignal(),
        "tiktok": TikTokSignal(),
        "shopify_saturation": SaturationSignal(),
        "aliexpress": None,
        "google_shopping": (None, None),
    }
    cleaned: list[Any] = []
    for label, res in zip(labels, results):
        if isinstance(res, Exception):
            warnings.append(f"{label} failed: {type(res).__name__}: {res}")
            cleaned.append(empties[label])
        else:
            cleaned.append(res)

    trends, meta, tt, sat, ali_median, gs = cleaned
    return trends, meta, tt, sat, ali_median, gs


def _build_price_signal(
    supplier_median: float | None,
    retail_median: float | None,
    retail_range: tuple[float, float] | None,
    fingerprint: ProductFingerprint,
) -> PriceSignal:
    effective_retail = retail_median or fingerprint.estimated_retail_price_usd
    margin_pct = None
    if effective_retail and supplier_median and effective_retail > 0:
        margin_pct = round(
            (effective_retail - supplier_median) / effective_retail * 100, 1
        )

    return PriceSignal(
        retail_price_median_usd=effective_retail,
        retail_price_range_usd=retail_range,
        supplier_price_median_usd=supplier_median,
        gross_margin_pct=margin_pct,
    )


def _build_sub_scores(
    trends: TrendsSignal,
    meta: MetaAdsSignal,
    sat: SaturationSignal,
    price: PriceSignal,
    season,
) -> list[SubScore]:
    return [
        scoring.score_momentum(trends.interest_over_time),
        scoring.score_saturation(sat),
        scoring.score_ad_velocity(meta),
        scoring.score_seasonality(season),
        scoring.score_margin(price),
    ]


class TrendAnalyzerSkill(BaseSkill[TrendAnalyzerInput, TrendAnalyzerOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Full-stack trend / saturation / creative analysis for dropshippers."
    consumes_credits = True
    credit_cost = 3

    async def run(
        self, input: TrendAnalyzerInput, ctx: SkillContext
    ) -> SkillResult[TrendAnalyzerOutput]:
        _validate_input(input)
        start = time.perf_counter()
        warnings: list[str] = []

        with tracker(
            cap_usd=settings.TREND_ANALYZER_COST_CAP_USD, force=input.force
        ) as cost:
            fingerprint = await _resolve_fingerprint(input, cost)

            (
                trends_sig,
                meta_sig,
                tiktok_sig,
                sat_sig,
                supplier_median,
                (retail_median, retail_range),
            ) = await _fetch_all_providers(fingerprint, input, cost, warnings)

            if trends_sig.stale:
                warnings.append("Google Trends data is stale or empty.")

            season = seasonality.detect(trends_sig.interest_over_time)
            price_sig = _build_price_signal(
                supplier_median, retail_median, retail_range, fingerprint
            )

            sub_scores = _build_sub_scores(
                trends_sig, meta_sig, sat_sig, price_sig, season
            )
            total_score = scoring.aggregate(sub_scores)
            verdict, rationale = scoring.decide(total_score, sub_scores)

            creatives = CreativesBlock()
            if not input.skip_creatives:
                try:
                    creatives = await creatives_gen.generate(
                        fingerprint, trends_sig, meta_sig, cost
                    )
                except Exception as exc:
                    logger.warning("creatives.generation_failed: %s", exc)
                    warnings.append(f"Creative generation failed: {exc}")

            report = TrendReport(
                fingerprint=fingerprint,
                score=total_score,
                verdict=verdict,
                rationale=rationale,
                sub_scores=sub_scores,
                interest_over_time=trends_sig.interest_over_time,
                seasonality=season,
                saturation=sat_sig,
                meta_ads=meta_sig,
                tiktok=tiktok_sig,
                geography=trends_sig.geography,
                price=price_sig,
                creatives=creatives,
                cost=cost.snapshot(),
                warnings=warnings,
            )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        output = TrendAnalyzerOutput(report=report, markdown=to_markdown(report))
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
