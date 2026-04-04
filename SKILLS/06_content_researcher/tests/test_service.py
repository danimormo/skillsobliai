"""Tests for the ContentResearcherSkill service."""

from __future__ import annotations

import importlib

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from core.skill_interface import SkillContext

_schemas = importlib.import_module("SKILLS.06_content_researcher.schemas")
ContentResearchInput = _schemas.ContentResearchInput

_service = importlib.import_module("SKILLS.06_content_researcher.service")
ContentResearcherSkill = _service.ContentResearcherSkill
_classify_format_type = _service._classify_format_type
_classify_creative_angle = _service._classify_creative_angle
_extract_hook = _service._extract_hook


@pytest.fixture
def ctx() -> SkillContext:
    return SkillContext(user_id="test_user_123")


@pytest.fixture
def skill() -> ContentResearcherSkill:
    return ContentResearcherSkill()


# ── Helpers ──────────────────────────────────────────────────────────────


class TestClassifyFormatType:
    def test_review_keyword(self):
        assert _classify_format_type("Honest review of this serum", "tiktok") == "review"

    def test_transformation_keyword(self):
        assert _classify_format_type("My skin transformation in 30 days", "tiktok") == "transformation"

    def test_demo_keyword(self):
        assert _classify_format_type("How to apply foundation tutorial", "tiktok") == "demo"

    def test_ugc_keyword(self):
        assert _classify_format_type("Try this with me!", "tiktok") == "ugc"

    def test_lifestyle_keyword(self):
        assert _classify_format_type("My morning routine aesthetic", "pinterest") == "lifestyle"

    def test_default_tiktok(self):
        assert _classify_format_type("just vibing", "tiktok") == "ugc"

    def test_default_pinterest(self):
        assert _classify_format_type("just vibing", "pinterest") == "lifestyle"


class TestClassifyCreativeAngle:
    def test_problem_solution(self):
        assert _classify_creative_angle("The problem with cheap protein") == "problem_solution"

    def test_social_proof(self):
        assert _classify_creative_angle("Everyone is obsessed with this") == "social_proof"

    def test_trend(self):
        assert _classify_creative_angle("This trending hack changed my life") == "trend"

    def test_default_lifestyle(self):
        assert _classify_creative_angle("Beautiful morning") == "lifestyle"


class TestExtractHook:
    def test_extracts_first_line(self):
        assert _extract_hook("Stop buying this!\nHere is why") == "Stop buying this!"

    def test_none_caption(self):
        assert _extract_hook(None) is None

    def test_empty_caption(self):
        assert _extract_hook("") is None


# ── Service tests ────────────────────────────────────────────────────────


_TIKTOK_RAW = [
    {
        "id": "tt_001",
        "url": "https://www.tiktok.com/@user/video/tt_001",
        "caption": "Honest review of this protein powder\nLink in bio",
        "likes": 5000,
        "views": 100000,
        "saves": 200,
        "thumbnail_url": "https://img.example.com/tt_001.jpg",
    },
    {
        "id": "tt_002",
        "url": "https://www.tiktok.com/@user/video/tt_002",
        "caption": "Try this viral hack for better sleep",
        "likes": 12000,
        "views": 300000,
        "saves": 800,
        "thumbnail_url": "https://img.example.com/tt_002.jpg",
    },
]

_PINTEREST_RAW = [
    {
        "id": "pin_001",
        "url": "https://www.pinterest.com/pin/pin_001/",
        "description": "Morning routine aesthetic inspo",
        "likes": 100,
        "saves": 500,
        "image_url": "https://img.example.com/pin_001.jpg",
    },
]


@pytest.mark.asyncio
async def test_run_returns_aggregated_output(skill: ContentResearcherSkill, ctx: SkillContext):
    """Service aggregates items from multiple platforms and computes insights."""
    input_data = ContentResearchInput(
        keywords=["protein"],
        platforms=["tiktok", "pinterest"],
        region="US",
        limit_per_platform=10,
    )

    with (
        patch("SKILLS.06_content_researcher.cache.get_cached", new_callable=AsyncMock, return_value=None),
        patch("SKILLS.06_content_researcher.cache.set_cached", new_callable=AsyncMock),
        patch("SKILLS.06_content_researcher.api_client.search_tiktok", new_callable=AsyncMock, return_value=_TIKTOK_RAW),
        patch("SKILLS.06_content_researcher.api_client.search_pinterest", new_callable=AsyncMock, return_value=_PINTEREST_RAW),
        patch("SKILLS.06_content_researcher.service.get_supabase") as mock_supa,
    ):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_supa.return_value.table.return_value = mock_table

        result = await skill.run(input_data, ctx)

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert result.data.total_items == 3
    assert len(result.data.items) == 3
    assert result.data.avg_engagement_rate > 0
    assert len(result.data.top_formats) > 0
    assert len(result.data.top_angles) > 0
    assert result.data.content_insights != ""


@pytest.mark.asyncio
async def test_run_returns_cached_result(skill: ContentResearcherSkill, ctx: SkillContext):
    """Service returns cached data without calling upstream APIs."""
    input_data = ContentResearchInput(
        keywords=["skincare"],
        platforms=["tiktok"],
    )

    cached_output = {
        "total_items": 1,
        "items": [
            {
                "platform": "tiktok",
                "content_id": "cached_001",
                "url": "https://tiktok.com/cached",
                "likes": 100,
                "engagement_rate": 0.05,
                "format_type": "ugc",
                "creative_angle": "lifestyle",
            }
        ],
        "top_formats": ["ugc"],
        "top_angles": ["lifestyle"],
        "avg_engagement_rate": 0.05,
        "content_insights": "Cached insights",
    }

    with (
        patch("SKILLS.06_content_researcher.cache.get_cached", new_callable=AsyncMock, return_value=cached_output),
        patch("SKILLS.06_content_researcher.api_client.search_tiktok", new_callable=AsyncMock) as mock_tt,
    ):
        result = await skill.run(input_data, ctx)

    assert result.success is True
    assert result.cached is True
    assert result.data.total_items == 1
    mock_tt.assert_not_called()


@pytest.mark.asyncio
async def test_run_validates_empty_keywords(skill: ContentResearcherSkill, ctx: SkillContext):
    """Service raises InvalidParamsError when keywords list is empty."""
    from core.errors import InvalidParamsError

    input_data = ContentResearchInput(
        keywords=[],
        platforms=["tiktok"],
    )

    with pytest.raises(InvalidParamsError, match="keywords must not be empty"):
        await skill.run(input_data, ctx)
