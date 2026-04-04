import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.01_meta_ads_researcher.schemas import MetaAdsResearchInput
from SKILLS.01_meta_ads_researcher.service import MetaAdsResearcherSkill
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return MetaAdsResearcherSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return MetaAdsResearchInput(
        search_terms=["protein powder"],
        countries=["IT"],
        active_only=True,
        limit_per_term=10,
    )


def _make_api_response(ad_id: str = "123", page_name: str = "TestPage") -> dict:
    return {
        "data": [
            {
                "ad_id": ad_id,
                "page_name": page_name,
                "page_id": "page_001",
                "body": "Buy now!",
                "title": "Best Product",
                "snapshot_url": "https://example.com/snap.png",
                "landing_url": "https://example.com/landing",
                "platforms": ["facebook"],
                "start_date": "2026-01-01",
                "end_date": None,
                "countries": ["IT"],
            }
        ]
    }


@pytest.mark.asyncio
async def test_run_happy_path(skill, ctx, sample_input):
    """Successful fetch returns deduplicated ads with computed fields."""
    with (
        patch(
            "SKILLS.01_meta_ads_researcher.cache.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "SKILLS.01_meta_ads_researcher.cache.set_cached",
            new_callable=AsyncMock,
        ),
        patch(
            "SKILLS.01_meta_ads_researcher.api_client.fetch_ads",
            new_callable=AsyncMock,
            return_value=_make_api_response(),
        ),
        patch(
            "SKILLS.01_meta_ads_researcher.service.get_supabase",
        ) as mock_sb,
    ):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert result.data.total_ads == 1
    assert result.data.ads[0].ad_id == "123"
    assert result.data.ads[0].is_active is True
    assert result.data.ads[0].days_running > 0


@pytest.mark.asyncio
async def test_run_upstream_error_skipped(skill, ctx, sample_input):
    """When upstream raises an exception, the error is logged and skipped."""
    with (
        patch(
            "SKILLS.01_meta_ads_researcher.cache.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "SKILLS.01_meta_ads_researcher.cache.set_cached",
            new_callable=AsyncMock,
        ),
        patch(
            "SKILLS.01_meta_ads_researcher.api_client.fetch_ads",
            new_callable=AsyncMock,
            side_effect=RuntimeError("connection lost"),
        ),
        patch(
            "SKILLS.01_meta_ads_researcher.service.get_supabase",
        ) as mock_sb,
    ):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.data is not None
    assert result.data.total_ads == 0


@pytest.mark.asyncio
async def test_run_cache_hit(skill, ctx, sample_input):
    """When cache contains data, upstream is never called."""
    cached_output = {
        "total_ads": 1,
        "ads": [
            {
                "ad_id": "cached_001",
                "page_name": "CachedPage",
                "page_id": "p1",
                "body": None,
                "title": None,
                "snapshot_url": "https://example.com/snap.png",
                "landing_url": None,
                "platforms": [],
                "start_date": "2026-01-01",
                "end_date": None,
                "is_active": True,
                "days_running": 90,
                "countries": ["IT"],
            }
        ],
        "search_terms": ["protein powder"],
        "countries": ["IT"],
        "next_cursor": None,
    }

    with (
        patch(
            "SKILLS.01_meta_ads_researcher.cache.get_cached",
            new_callable=AsyncMock,
            return_value=cached_output,
        ),
        patch(
            "SKILLS.01_meta_ads_researcher.api_client.fetch_ads",
            new_callable=AsyncMock,
        ) as mock_fetch,
    ):
        result = await skill.run(sample_input, ctx)

    mock_fetch.assert_not_awaited()
    assert result.success is True
    assert result.cached is True
    assert result.data is not None
    assert result.data.ads[0].ad_id == "cached_001"
