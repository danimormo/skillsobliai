from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.pdp_builder.schemas import PDPBuilderInput
from SKILLS.pdp_builder.service import PDPBuilderSkill
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return PDPBuilderSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return PDPBuilderInput(
        product_title="Super Serum",
        product_description="Anti-aging face serum",
        price=29.99,
        copy_angle="benefit",
        language="en",
    )


def _make_api_response() -> dict:
    return {
        "headlines": ["Look 10 Years Younger", "Glow Like Never Before"],
        "subheadline": "The #1 anti-aging serum loved by dermatologists",
        "benefit_bullets": [
            "Reduces wrinkles in 2 weeks",
            "Hydrates for 24 hours",
        ],
        "description_long": "Super Serum is a breakthrough formula.",
        "faq": [
            {"question": "How often should I use it?", "answer": "Twice daily."}
        ],
        "urgency_text": "Only 50 left in stock!",
        "cta_text": "Add to Cart",
    }


@pytest.mark.asyncio
async def test_run_happy_path(skill, ctx, sample_input):
    """Successful generation returns structured PDP sections."""
    with (
        patch(
            "SKILLS.pdp_builder.cache.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "SKILLS.pdp_builder.cache.set_cached",
            new_callable=AsyncMock,
        ),
        patch(
            "SKILLS.pdp_builder.api_client.generate_pdp",
            new_callable=AsyncMock,
            return_value=_make_api_response(),
        ),
        patch(
            "SKILLS.pdp_builder.service.get_supabase",
        ) as mock_sb,
    ):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert len(result.data.sections.headlines) == 2
    assert result.data.copy_angle == "benefit"
    assert result.data.word_count > 0


@pytest.mark.asyncio
async def test_run_cache_hit(skill, ctx, sample_input):
    """When cache contains data, upstream is never called."""
    cached_output = {
        "pdp_id": "cached-pdp-001",
        "sections": {
            "headlines": ["Cached Headline"],
            "subheadline": "Cached sub",
            "benefit_bullets": ["Bullet 1"],
            "description_long": "Cached description.",
            "faq": [],
            "urgency_text": "Hurry!",
            "cta_text": "Buy Now",
        },
        "copy_angle": "benefit",
        "language": "en",
        "word_count": 10,
    }

    with (
        patch(
            "SKILLS.pdp_builder.cache.get_cached",
            new_callable=AsyncMock,
            return_value=cached_output,
        ),
        patch(
            "SKILLS.pdp_builder.api_client.generate_pdp",
            new_callable=AsyncMock,
        ) as mock_gen,
    ):
        result = await skill.run(sample_input, ctx)

    mock_gen.assert_not_awaited()
    assert result.success is True
    assert result.cached is True
    assert result.data.pdp_id == "cached-pdp-001"


@pytest.mark.asyncio
async def test_validate_empty_title(skill, ctx):
    """Empty product_title raises InvalidParamsError."""
    bad_input = PDPBuilderInput(
        product_title="   ",
        price=10.0,
    )
    from core.errors import InvalidParamsError

    with pytest.raises(InvalidParamsError):
        skill.validate(bad_input)
