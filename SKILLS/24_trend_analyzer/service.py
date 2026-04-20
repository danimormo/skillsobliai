"""Trend Analyzer skill — Phase 1 skeleton.

Orchestrates normalization + tier-1 providers + scoring + LLM creatives.
Phase 2 will wire the real providers; for now this module exposes the
skeleton class and argument-validation so the router can be mounted and
return a structured empty report without crashing.
"""

from __future__ import annotations

import logging
import time

from core.config import settings
from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult

from . import cache
from .cost_tracker import tracker
from .schemas import (
    ProductFingerprint,
    SubScore,
    TrendAnalyzerInput,
    TrendAnalyzerOutput,
    TrendReport,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "trend-analyzer"


# Sub-score weights (must sum to 1.0)
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


class TrendAnalyzerSkill(BaseSkill[TrendAnalyzerInput, TrendAnalyzerOutput]):
    name = SKILL_NAME
    version = "0.1.0"
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
            # ── Phase 1 placeholder: return an empty report ─────────
            # Phase 2 will fill: normalize → providers → scoring → creatives.
            fingerprint = ProductFingerprint(
                primary_keyword=(input.text or "").strip() or "pending",
                source_kind=(
                    "text" if input.text else "url" if input.url else "image"
                ),
                raw_input=str(input.text or input.url or input.image_url or "<b64>"),
            )

            sub_scores = [
                SubScore(
                    name=n,  # type: ignore[arg-type]
                    value=0.0,
                    weight=WEIGHTS[n],
                    explanation="Phase 2: not yet implemented.",
                )
                for n in WEIGHTS
            ]

            report = TrendReport(
                fingerprint=fingerprint,
                score=0.0,
                verdict="WAIT",
                rationale="Skill skeleton only — providers land in Phase 2.",
                sub_scores=sub_scores,
                cost=cost.snapshot(),
                warnings=["Phase 1 skeleton — no live data yet."],
            )

            output = TrendAnalyzerOutput(report=report, markdown="")

            if not input.no_cache:
                await cache.set("fingerprint", fingerprint.primary_keyword, fingerprint.model_dump())

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
