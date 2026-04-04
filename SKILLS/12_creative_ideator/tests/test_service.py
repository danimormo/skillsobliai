from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.creative_ideator.schemas import CreativeIdeatorInput
from SKILLS.creative_ideator.service import CreativeIdeatorSkill
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return CreativeIdeatorSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return CreativeIdeatorInput(
        product_title="Super Serum",
        product_description="Anti-aging face serum with hyaluronic acid",
        num_angles=2,
        platform="meta",
        language="en",
    )


def _make_api_response() -> dict:
    return {
        "angles": [
            {
                "name": "Before/After Transformation",
                "hook": "Watch my skin transform in just 14 days",
                "script_30s": "I was skeptical at first...",
                "format": "UGC",
                "visual_refs": ["before-after split screen", "close-up skin texture"],
                "target_emotion": "hope",
                "estimated_ctr_tier": "high",
            },
            {
                "name": "Expert Authority",
                "hook": "Dermatologists are calling this a game-changer",
                "script_30s": "Leading dermatologists now recommend...",
                "format": "static",
                "visual_refs": ["lab coat professional", "clinical setting"],
                "target_emotion": "trust",
                "estimated_ctr_tier": "medium",
            },
        ],
        "recommended_angle": "Before/After Transformation",
    }


@pytest.mark.asyncio
async def test_run_happy_path(skill, ctx, sample_input):
    """Successful generation returns creative angles."""
    with (
        patch(
            "SKILLS.creative_ideator.cache.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "SKILLS.creative_ideator.cache.set_cached",
            new_callable=AsyncMock,
        ),
        patch(
            "SKILLS.creative_ideator.api_client.generate_creative_angles",
            new_callable=AsyncMock,
            return_value=_make_api_response(),
        ),
        patch(
            "SKILLS.creative_ideator.service.get_supabase",
        ) as mock_sb,
    ):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert len(result.data.angles) == 2
    assert result.data.recommended_angle == "Before/After Transformation"
    assert result.data.platform == "meta"


@pytest.mark.asyncio
async def test_run_cache_hit(skill, ctx, sample_input):
    """When cache contains data, upstream is never called."""
    cached_output = {
        "product_title": "Super Serum",
        "angles": [
            {
                "name": "Cached Angle",
                "hook": "Cached hook",
                "script_30s": "Cached script",
                "format": "UGC",
                "visual_refs": [],
                "target_emotion": "curiosity",
                "estimated_ctr_tier": "high",
            }
        ],
        "recommended_angle": "Cached Angle",
        "platform": "meta",
    }

    with (
        patch(
            "SKILLS.creative_ideator.cache.get_cached",
            new_callable=AsyncMock,
            return_value=cached_output,
        ),
        patch(
            "SKILLS.creative_ideator.api_client.generate_creative_angles",
            new_callable=AsyncMock,
        ) as mock_gen,
    ):
        result = await skill.run(sample_input, ctx)

    mock_gen.assert_not_awaited()
    assert result.success is True
    assert result.cached is True
    assert result.data.angles[0].name == "Cached Angle"


@pytest.mark.asyncio
async def test_validate_empty_title(skill):
    """Empty product_title raises InvalidParamsError."""
    bad_input = CreativeIdeatorInput(
        product_title="   ",
        product_description="Some description",
    )
    from core.errors import InvalidParamsError

    with pytest.raises(InvalidParamsError):
        skill.validate(bad_input)
