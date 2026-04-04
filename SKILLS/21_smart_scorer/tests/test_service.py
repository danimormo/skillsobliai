import pytest

from SKILLS.smart_scorer.schemas import SmartScorerInput
from SKILLS.smart_scorer.service import SmartScorerSkill, calculate_score
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return SmartScorerSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


def test_calculate_score_high():
    """High-signal product should score S-tier."""
    data = SmartScorerInput(
        product_title="Super Gadget",
        total_ads=100,
        active_ads=90,
        found_on_meta=True,
        found_on_tiktok=True,
        found_on_pinterest=True,
        shopify_store_count=5,
        avg_engagement_rate=0.08,
        estimated_margin_pct=0.7,
    )
    score, breakdown = calculate_score(data)
    # trend: int(0.9*25)=22, platform: min(21,20)=20, sat: 25, margin: 20, engagement: 10
    assert score >= 80
    assert breakdown["trend_momentum"] == 22
    assert breakdown["multi_platform"] == 20
    assert breakdown["saturation_inverse"] == 25
    assert breakdown["margin"] == 20
    assert breakdown["engagement"] == 10


def test_calculate_score_low():
    """Low-signal product should score D-tier."""
    data = SmartScorerInput(
        product_title="Generic Item",
        total_ads=0,
        active_ads=0,
        found_on_meta=False,
        found_on_tiktok=False,
        found_on_pinterest=False,
        shopify_store_count=600,
        avg_engagement_rate=0.001,
        estimated_margin_pct=0.1,
    )
    score, breakdown = calculate_score(data)
    assert score < 25
    assert breakdown["trend_momentum"] == 0
    assert breakdown["multi_platform"] == 0
    assert breakdown["saturation_inverse"] == 0
    assert breakdown["margin"] == 0
    assert breakdown["engagement"] == 0


@pytest.mark.asyncio
async def test_run_returns_tier_and_recommendation(skill, ctx):
    """Service run returns correct tier label and recommendation string."""
    inp = SmartScorerInput(
        product_title="Mid Product",
        total_ads=20,
        active_ads=10,
        found_on_meta=True,
        found_on_tiktok=False,
        found_on_pinterest=False,
        shopify_store_count=30,
        avg_engagement_rate=0.03,
        estimated_margin_pct=0.45,
    )
    result = await skill.run(inp, ctx)

    assert result.success is True
    data = result.data
    # trend: int(0.5*25)=12, platform: 7, sat: 18, margin: 12, engagement: 5 -> 54 => B
    assert data.score == 54
    assert data.tier == "B"
    assert "Moderate" in data.recommendation
    assert data.product_title == "Mid Product"
