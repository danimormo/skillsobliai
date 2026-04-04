from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.landing_builder.schemas import LandingBuilderInput
from SKILLS.landing_builder.service import LandingBuilderSkill
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return LandingBuilderSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return LandingBuilderInput(
        product_title="Super Serum",
        product_description="Anti-aging face serum",
        price=29.99,
        target_audience="Women 25-45",
        main_benefit="Reduces wrinkles in 2 weeks",
        cta_destination_url="https://example.com/buy",
        language="en",
    )


def _make_api_response() -> list[dict]:
    return [
        {
            "type": "hero",
            "headline": "Transform Your Skin",
            "body": "Discover the serum that changed everything.",
            "cta_text": "Shop Now",
        },
        {
            "type": "benefits",
            "headline": "Why Super Serum?",
            "body": "Clinically proven results in just 14 days.",
            "cta_text": None,
        },
    ]


@pytest.mark.asyncio
async def test_run_happy_path(skill, ctx, sample_input):
    """Successful generation returns structured landing sections."""
    with (
        patch(
            "SKILLS.landing_builder.cache.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "SKILLS.landing_builder.cache.set_cached",
            new_callable=AsyncMock,
        ),
        patch(
            "SKILLS.landing_builder.api_client.generate_landing",
            new_callable=AsyncMock,
            return_value=_make_api_response(),
        ),
        patch(
            "SKILLS.landing_builder.service.get_supabase",
        ) as mock_sb,
    ):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert len(result.data.sections) == 2
    assert result.data.sections[0].type == "hero"
    assert result.data.total_word_count > 0


@pytest.mark.asyncio
async def test_run_cache_hit(skill, ctx, sample_input):
    """When cache contains data, upstream is never called."""
    cached_output = {
        "landing_id": "cached-landing-001",
        "sections": [
            {
                "type": "hero",
                "headline": "Cached Headline",
                "body": "Cached body.",
                "cta_text": "Buy",
            }
        ],
        "total_word_count": 5,
        "language": "en",
    }

    with (
        patch(
            "SKILLS.landing_builder.cache.get_cached",
            new_callable=AsyncMock,
            return_value=cached_output,
        ),
        patch(
            "SKILLS.landing_builder.api_client.generate_landing",
            new_callable=AsyncMock,
        ) as mock_gen,
    ):
        result = await skill.run(sample_input, ctx)

    mock_gen.assert_not_awaited()
    assert result.success is True
    assert result.cached is True
    assert result.data.landing_id == "cached-landing-001"


@pytest.mark.asyncio
async def test_validate_empty_title(skill, ctx):
    """Empty product_title raises InvalidParamsError."""
    bad_input = LandingBuilderInput(
        product_title="   ",
        product_description="Desc",
        price=10.0,
        target_audience="Everyone",
        main_benefit="Great",
        cta_destination_url="https://example.com",
    )
    from core.errors import InvalidParamsError

    with pytest.raises(InvalidParamsError):
        skill.validate(bad_input)
