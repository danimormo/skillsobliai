from unittest.mock import AsyncMock, patch

import pytest

from SKILLS.saturation_detector.schemas import SaturationDetectorInput
from SKILLS.saturation_detector.service import (
    SaturationDetectorSkill,
    _classify,
    _matches_product,
)
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return SaturationDetectorSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return SaturationDetectorInput(
        product_title="LED posture corrector",
        product_keywords=["posture belt"],
        sample_size=5,
    )


SAMPLE_STORES = ["store1.myshopify.com", "store2.myshopify.com", "store3.myshopify.com",
                  "store4.myshopify.com", "store5.myshopify.com"]


@pytest.mark.asyncio
async def test_run_happy_path(skill, ctx, sample_input):
    """Successful scan returns saturation output with correct classification."""
    with (
        patch(
            "SKILLS.saturation_detector.cache.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "SKILLS.saturation_detector.cache.set_cached",
            new_callable=AsyncMock,
        ),
        patch(
            "SKILLS.saturation_detector.service._load_store_list",
            return_value=SAMPLE_STORES,
        ),
        patch(
            "SKILLS.saturation_detector.api_client.fetch_store_products",
            new_callable=AsyncMock,
            return_value=[{"title": "LED posture corrector belt"}],
        ),
    ):
        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert result.data.stores_sampled == 5
    assert result.data.stores_found == 5
    assert result.data.saturation_level == "very_high"
    assert result.data.flag == "red"


@pytest.mark.asyncio
async def test_run_cache_hit(skill, ctx, sample_input):
    """When cache contains data, store scanning is skipped."""
    cached_output = {
        "product_title": "LED posture corrector",
        "stores_found": 2,
        "stores_sampled": 50,
        "saturation_index": 0.04,
        "saturation_level": "low",
        "flag": "green",
        "recommendation": "Low saturation.",
        "found_in_stores": ["store1.myshopify.com", "store2.myshopify.com"],
    }

    with (
        patch(
            "SKILLS.saturation_detector.cache.get_cached",
            new_callable=AsyncMock,
            return_value=cached_output,
        ),
        patch(
            "SKILLS.saturation_detector.api_client.fetch_store_products",
            new_callable=AsyncMock,
        ) as mock_fetch,
    ):
        result = await skill.run(sample_input, ctx)

    mock_fetch.assert_not_awaited()
    assert result.success is True
    assert result.cached is True
    assert result.data.stores_found == 2


@pytest.mark.asyncio
async def test_run_no_matches(skill, ctx, sample_input):
    """When no stores carry the product, saturation is zero."""
    with (
        patch(
            "SKILLS.saturation_detector.cache.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "SKILLS.saturation_detector.cache.set_cached",
            new_callable=AsyncMock,
        ),
        patch(
            "SKILLS.saturation_detector.service._load_store_list",
            return_value=SAMPLE_STORES,
        ),
        patch(
            "SKILLS.saturation_detector.api_client.fetch_store_products",
            new_callable=AsyncMock,
            return_value=[{"title": "Completely unrelated product XYZ"}],
        ),
    ):
        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.data.stores_found == 0
    assert result.data.saturation_index == 0.0
    assert result.data.saturation_level == "low"
    assert result.data.flag == "green"
