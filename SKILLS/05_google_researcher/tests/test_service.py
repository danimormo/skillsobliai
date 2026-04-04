"""Tests for GoogleResearcherSkill service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.skill_interface import SkillContext
from SKILLS.05_google_researcher.schemas import GoogleResearchInput
from SKILLS.05_google_researcher.service import GoogleResearcherSkill

SKILL = GoogleResearcherSkill()


def _make_ctx(user_id: str = "test-user") -> SkillContext:
    return SkillContext(user_id=user_id)


def _fake_trends(values: list[int] | None = None) -> dict:
    if values is None:
        values = [30, 35, 40, 50, 60, 70, 85, 90, 80, 75]
    return {
        "interest_over_time": [
            {"date": f"2025-01-{i + 1:02d}", "value": v}
            for i, v in enumerate(values)
        ],
        "estimated_monthly_searches": 12000,
        "estimated_cpc_usd": 1.25,
    }


def _fake_reddit_posts(count: int = 3) -> list[dict]:
    return [
        {
            "title": f"Great product review number {i}",
            "subreddit": "dropshipping",
            "score": 15 * (i + 1),
            "url": f"https://reddit.com/r/dropshipping/post{i}",
        }
        for i in range(count)
    ]


@pytest.mark.asyncio
async def test_run_returns_rising_trend():
    """When last-30-day avg > first-30-day avg * 1.15, direction is rising."""
    inp = GoogleResearchInput(keywords=["led lamp"])
    ctx = _make_ctx()

    with (
        patch("SKILLS.05_google_researcher.service.cache.get_cached", new_callable=AsyncMock, return_value=None),
        patch("SKILLS.05_google_researcher.service.cache.set_cached", new_callable=AsyncMock),
        patch("SKILLS.05_google_researcher.service.api_client.fetch_google_trends", new_callable=AsyncMock, return_value=_fake_trends([20, 25, 30, 30, 35, 60, 70, 80, 85, 90])),
        patch("SKILLS.05_google_researcher.service.api_client.search_reddit", new_callable=AsyncMock, return_value=_fake_reddit_posts()),
        patch("SKILLS.05_google_researcher.service.get_supabase") as mock_sb,
    ):
        mock_sb.return_value = MagicMock()
        mock_sb.return_value.table.return_value.insert.return_value.execute.return_value = None

        result = await SKILL.run(inp, ctx)

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert result.data.keyword == "led lamp"
    assert result.data.trend_direction == "rising"
    assert result.data.demand_score >= 0


@pytest.mark.asyncio
async def test_run_returns_cached_result():
    """When cache hit, return cached data without calling upstream APIs."""
    cached = {
        "keyword": "yoga mat",
        "trend_direction": "stable",
        "trend_data": [{"date": "2025-01-01", "value": 50}],
        "peak_months": [],
        "reddit_posts": [],
        "overall_sentiment": "neutral",
        "demand_score": 30,
    }
    inp = GoogleResearchInput(keywords=["yoga mat"])
    ctx = _make_ctx()

    with (
        patch("SKILLS.05_google_researcher.service.cache.get_cached", new_callable=AsyncMock, return_value=cached),
        patch("SKILLS.05_google_researcher.service.api_client.fetch_google_trends", new_callable=AsyncMock) as mock_trends,
    ):
        result = await SKILL.run(inp, ctx)

    assert result.success is True
    assert result.cached is True
    assert result.data.keyword == "yoga mat"
    mock_trends.assert_not_called()


@pytest.mark.asyncio
async def test_run_computes_sentiment_and_demand_score():
    """Verify sentiment assignment and demand score calculation."""
    posts = [
        {"title": "Amazing product", "subreddit": "gadgets", "score": 50, "url": "https://reddit.com/1"},
        {"title": "Terrible experience", "subreddit": "gadgets", "score": -5, "url": "https://reddit.com/2"},
        {"title": "Meh not great", "subreddit": "gadgets", "score": 3, "url": "https://reddit.com/3"},
    ]
    inp = GoogleResearchInput(keywords=["wireless charger"])
    ctx = _make_ctx()

    with (
        patch("SKILLS.05_google_researcher.service.cache.get_cached", new_callable=AsyncMock, return_value=None),
        patch("SKILLS.05_google_researcher.service.cache.set_cached", new_callable=AsyncMock),
        patch("SKILLS.05_google_researcher.service.api_client.fetch_google_trends", new_callable=AsyncMock, return_value=_fake_trends([50] * 10)),
        patch("SKILLS.05_google_researcher.service.api_client.search_reddit", new_callable=AsyncMock, return_value=posts),
        patch("SKILLS.05_google_researcher.service.get_supabase") as mock_sb,
    ):
        mock_sb.return_value = MagicMock()
        mock_sb.return_value.table.return_value.insert.return_value.execute.return_value = None

        result = await SKILL.run(inp, ctx)

    data = result.data
    sentiments = [p.sentiment for p in data.reddit_posts]
    assert sentiments == ["positive", "negative", "neutral"]
    assert data.overall_sentiment == "positive"  # most common (tied but positive first)
    assert 0 <= data.demand_score <= 100
