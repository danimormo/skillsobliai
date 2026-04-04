import logging
import time

from core.skill_interface import BaseSkill, SkillContext, SkillResult

from SKILLS.smart_scorer.schemas import SmartScorerInput, SmartScorerOutput

logger = logging.getLogger(__name__)

SKILL_NAME = "smart-scorer"

TIER_RECOMMENDATIONS = {
    "S": "Strong buy signal. Launch immediately with aggressive budget.",
    "A": "Good opportunity. Test with moderate budget and monitor closely.",
    "B": "Moderate potential. Consider testing with a small budget.",
    "C": "Weak signal. Research further before committing ad spend.",
    "D": "Not recommended. High saturation or low engagement indicators.",
}


def calculate_score(data: SmartScorerInput) -> tuple[int, dict]:
    """Compute the multi-source product score (0-100) with breakdown."""
    breakdown: dict[str, int] = {}
    score = 0

    # trend momentum 0-25
    active_ratio = data.active_ads / max(data.total_ads, 1)
    trend_pts = int(active_ratio * 25)
    breakdown["trend_momentum"] = trend_pts
    score += trend_pts

    # multi-platform 0-20
    platforms = sum([data.found_on_meta, data.found_on_tiktok, data.found_on_pinterest])
    platform_pts = min(platforms * 7, 20)
    breakdown["multi_platform"] = platform_pts
    score += platform_pts

    # saturation inverse 0-25
    if data.shopify_store_count < 10:
        sat_pts = 25
    elif data.shopify_store_count < 50:
        sat_pts = 18
    elif data.shopify_store_count < 200:
        sat_pts = 10
    elif data.shopify_store_count < 500:
        sat_pts = 4
    else:
        sat_pts = 0
    breakdown["saturation_inverse"] = sat_pts
    score += sat_pts

    # margin 0-20
    margin_pts = 0
    if data.estimated_margin_pct:
        if data.estimated_margin_pct > 0.6:
            margin_pts = 20
        elif data.estimated_margin_pct > 0.4:
            margin_pts = 12
        elif data.estimated_margin_pct > 0.25:
            margin_pts = 6
    breakdown["margin"] = margin_pts
    score += margin_pts

    # engagement 0-10
    engagement_pts = 0
    if data.avg_engagement_rate:
        if data.avg_engagement_rate > 0.05:
            engagement_pts = 10
        elif data.avg_engagement_rate > 0.02:
            engagement_pts = 5
    breakdown["engagement"] = engagement_pts
    score += engagement_pts

    return min(score, 100), breakdown


def _score_to_tier(score: int) -> str:
    if score >= 80:
        return "S"
    if score >= 65:
        return "A"
    if score >= 45:
        return "B"
    if score >= 25:
        return "C"
    return "D"


class SmartScorerSkill(BaseSkill[SmartScorerInput, SmartScorerOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Multi-source product scoring engine"
    consumes_credits = False
    credit_cost = 0

    def validate(self, input: SmartScorerInput) -> bool:
        return True

    async def run(
        self, input: SmartScorerInput, ctx: SkillContext
    ) -> SkillResult[SmartScorerOutput]:
        start = time.perf_counter()

        score, breakdown = calculate_score(input)
        tier = _score_to_tier(score)
        recommendation = TIER_RECOMMENDATIONS[tier]

        output = SmartScorerOutput(
            product_title=input.product_title,
            score=score,
            tier=tier,
            breakdown=breakdown,
            recommendation=recommendation,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
