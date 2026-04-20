"""Trend Analyzer skill — Phase 2a (normalizers wired).

Phase 2b will plug in providers (trends, meta ads, tiktok, shopify, ...);
for now we normalize the input into a ProductFingerprint and return an
otherwise-empty scaffold so the fingerprint is already observable via
``/api/skills/trend-analyzer/run``.
"""

from __future__ import annotations

import logging
import time

from core.config import settings
from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult

from . import cache
from .cost_tracker import CostTracker, tracker
from .normalize.image import normalize_image
from .normalize.text import normalize_text
from .normalize.url import normalize_url
from .schemas import (
    ProductFingerprint,
    SubScore,
    TrendAnalyzerInput,
    TrendAnalyzerOutput,
    TrendReport,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "trend-analyzer"


WEIGHTS: dict[str, float] = {
    "momentum": 0.30,
    "saturation": 0.25,
    "ad_velocity": 0.20,
    "seasonality": 0.15,
    "margin": 0.10,
}


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
    """Dispatch to the right normalizer, with cache for text inputs only.

    URL and image normalizers could in principle be cached too, but since the
    LLM cost is always paid on cache miss and the payload is small, we cache
    the resulting fingerprint keyed by the canonical input string.
    """
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


class TrendAnalyzerSkill(BaseSkill[TrendAnalyzerInput, TrendAnalyzerOutput]):
    name = SKILL_NAME
    version = "0.2.0"
    description = "Full-stack trend / saturation / creative analysis for dropshippers."
    consumes_credits = True
    credit_cost = 3

    async def run(
        self, input: TrendAnalyzerInput, ctx: SkillContext
    ) -> SkillResult[TrendAnalyzerOutput]:
        _validate_input(input)
        start = time.perf_counter()

        with tracker(
            cap_usd=settings.TREND_ANALYZER_COST_CAP_USD, force=input.force
        ) as cost:
            fingerprint = await _resolve_fingerprint(input, cost)

            sub_scores = [
                SubScore(
                    name=n,  # type: ignore[arg-type]
                    value=0.0,
                    weight=WEIGHTS[n],
                    explanation="Phase 2b: providers not yet implemented.",
                )
                for n in WEIGHTS
            ]

            report = TrendReport(
                fingerprint=fingerprint,
                score=0.0,
                verdict="WAIT",
                rationale="Normalization done; trend/saturation providers pending.",
                sub_scores=sub_scores,
                cost=cost.snapshot(),
                warnings=["Phase 2a — providers still pending."],
            )
            output = TrendAnalyzerOutput(report=report, markdown="")

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
