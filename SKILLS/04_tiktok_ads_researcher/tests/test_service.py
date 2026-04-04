from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.skill_interface import SkillContext
from SKILLS.04_tiktok_ads_researcher.schemas import (
    TikTokAdsResearchInput,
    TikTokAdsResearchOutput,
)
from SKILLS.04_tiktok_ads_researcher.service import TikTokAdsResearcherSkill


def _make_ctx(user_id: str = "user-1") -> SkillContext:
    return SkillContext(user_id=user_id)


def _fake_api_response(region: str = "US") -> dict:
    return {
        "ads": [
            {
                "ad_id": "ad-001",
                "advertiser_name": "TestBrand",
                "video_url": "https://example.com/video.mp4",
                "thumbnail_url": "https://example.com/thumb.jpg",
                "caption": "Buy now!",
                "cta_text": "Shop",
                "likes": 5000,
                "comments": 120,
                "shares": 300,
                "engagement_rate": 3.8,
                "estimated_spend": "$1,000-$5,000",
                "region": region,
                "industry": "ecommerce",
                "duration_seconds": 15.0,
                "is_active": True,
            }
        ]
    }


@pytest.fixture
def skill() -> TikTokAdsResearcherSkill:
    return TikTokAdsResearcherSkill()


@pytest.fixture
def input_data() -> TikTokAdsResearchInput:
    return TikTokAdsResearchInput(
        keywords=["skincare"],
        regions=["US"],
        industry="ecommerce",
        days_range=30,
        limit=50,
    )


# ------------------------------------------------------------------
# Happy path
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_happy_path(skill: TikTokAdsResearcherSkill, input_data: TikTokAdsResearchInput) -> None:
    """Skill fetches ads, deduplicates, persists, caches, and returns output."""
    mock_supabase_chain = MagicMock()
    mock_supabase_chain.table.return_value.insert.return_value.execute.return_value = None

    with (
        patch(
            "SKILLS.04_tiktok_ads_researcher.service.api_client.fetch_ads",
            new_callable=AsyncMock,
            return_value=_fake_api_response("US"),
        ) as mock_fetch,
        patch(
            "SKILLS.04_tiktok_ads_researcher.service.cache.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "SKILLS.04_tiktok_ads_researcher.service.cache.set_cached",
            new_callable=AsyncMock,
        ) as mock_set_cache,
        patch(
            "SKILLS.04_tiktok_ads_researcher.service.get_supabase",
            return_value=mock_supabase_chain,
        ),
    ):
        result = await skill.run(input_data, _make_ctx())

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert isinstance(result.data, TikTokAdsResearchOutput)
    assert result.data.total_ads == 1
    assert result.data.ads[0].ad_id == "ad-001"
    assert result.data.keywords == ["skincare"]
    assert result.data.regions == ["US"]

    mock_fetch.assert_awaited_once()
    mock_set_cache.assert_awaited_once()
    mock_supabase_chain.table.assert_called_once_with("research_results")


# ------------------------------------------------------------------
# Upstream error propagation
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_upstream_error(skill: TikTokAdsResearcherSkill, input_data: TikTokAdsResearchInput) -> None:
    """Skill propagates UpstreamError when the API client raises."""
    from core.errors import UpstreamError

    with (
        patch(
            "SKILLS.04_tiktok_ads_researcher.service.cache.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "SKILLS.04_tiktok_ads_researcher.service.api_client.fetch_ads",
            new_callable=AsyncMock,
            side_effect=UpstreamError(
                message="Upstream returned 500",
                skill="tiktok-ads-researcher",
                code="UPSTREAM_ERROR",
            ),
        ),
        pytest.raises(UpstreamError),
    ):
        await skill.run(input_data, _make_ctx())


# ------------------------------------------------------------------
# Cache hit
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_cache_hit(skill: TikTokAdsResearcherSkill, input_data: TikTokAdsResearchInput) -> None:
    """Skill returns cached data without calling the API."""
    cached_output = TikTokAdsResearchOutput(
        total_ads=1,
        ads=[
            {
                "ad_id": "ad-cached",
                "advertiser_name": "Cached Brand",
                "likes": 100,
                "comments": 10,
                "shares": 5,
                "engagement_rate": 2.0,
                "region": "US",
                "is_active": True,
            }
        ],
        keywords=["skincare"],
        regions=["US"],
    )

    with (
        patch(
            "SKILLS.04_tiktok_ads_researcher.service.cache.get_cached",
            new_callable=AsyncMock,
            return_value=cached_output.model_dump(),
        ),
        patch(
            "SKILLS.04_tiktok_ads_researcher.service.api_client.fetch_ads",
            new_callable=AsyncMock,
        ) as mock_fetch,
    ):
        result = await skill.run(input_data, _make_ctx())

    assert result.success is True
    assert result.cached is True
    assert result.data is not None
    assert result.data.total_ads == 1
    assert result.data.ads[0].ad_id == "ad-cached"

    mock_fetch.assert_not_awaited()
