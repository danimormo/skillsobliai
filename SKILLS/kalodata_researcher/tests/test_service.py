"""Tests for KalodataResearcherSkill service."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.skill_interface import SkillContext

from SKILLS.kalodata_researcher.schemas import KalodataResearchInput, KalodataResearchOutput
from SKILLS.kalodata_researcher.service import KalodataResearcherSkill


def _make_ctx(user_id: str = "test-user-1") -> SkillContext:
    return SkillContext(user_id=user_id)


def _make_input(**overrides) -> KalodataResearchInput:
    defaults = {"keywords": ["dog toy"], "region": "US", "days_range": 30, "limit": 5}
    defaults.update(overrides)
    return KalodataResearchInput(**defaults)


def _fake_product(pid: str = "p1", gmv_growth: float = 50.0, units: int = 1000, shops: int = 2) -> dict:
    return {
        "product_id": pid,
        "title": f"Product {pid}",
        "category": "Pets",
        "price_range": {"min": 5.0, "max": 15.0, "currency": "USD"},
        "gmv_30d": 50000.0,
        "gmv_growth_pct": gmv_growth,
        "units_sold_30d": units,
        "shop_count": shops,
        "top_shop": "BestShop",
        "thumbnail_url": "https://img.example.com/p1.jpg",
    }


def _fake_analytics(gmv_growth: float = 50.0, units: int = 1000, shops: int = 2) -> dict:
    return {
        "gmv_growth_pct": gmv_growth,
        "units_sold_30d": units,
        "shop_count": shops,
        "gmv_30d": 50000.0,
        "top_shop": "BestShop",
    }


@pytest.mark.asyncio
async def test_happy_path():
    """Full run: search returns products, analytics enriches them, result is cached and persisted."""
    skill = KalodataResearcherSkill()
    inp = _make_input()
    ctx = _make_ctx()

    with (
        patch(
            "SKILLS.kalodata_researcher.service.get_cached", new_callable=AsyncMock, return_value=None
        ),
        patch(
            "SKILLS.kalodata_researcher.service.set_cached", new_callable=AsyncMock
        ) as mock_set_cache,
        patch(
            "SKILLS.kalodata_researcher.service.search_products",
            new_callable=AsyncMock,
            return_value=[_fake_product("p1"), _fake_product("p2", gmv_growth=30.0)],
        ),
        patch(
            "SKILLS.kalodata_researcher.service.get_product_analytics",
            new_callable=AsyncMock,
            return_value=_fake_analytics(),
        ),
        patch("SKILLS.kalodata_researcher.service.get_supabase") as mock_sb,
    ):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(inp, ctx)

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert result.data.total_products == 2
    assert result.data.region == "US"
    # Products should be sorted by opportunity_score desc
    scores = [p.opportunity_score for p in result.data.products]
    assert scores == sorted(scores, reverse=True)
    # Cache should have been set
    mock_set_cache.assert_awaited_once()


@pytest.mark.asyncio
async def test_cache_hit():
    """When cache holds a result, skip API calls and return cached output."""
    skill = KalodataResearcherSkill()
    inp = _make_input()
    ctx = _make_ctx()

    cached_data = {
        "total_products": 1,
        "products": [
            {
                "product_id": "cached-1",
                "title": "Cached Product",
                "category": "Pets",
                "price_range": {"min": 1, "max": 10, "currency": "USD"},
                "gmv_30d": 10000,
                "gmv_growth_pct": 20.0,
                "units_sold_30d": 500,
                "shop_count": 1,
                "top_shop": None,
                "opportunity_score": 10000.0,
                "thumbnail_url": None,
            }
        ],
        "region": "US",
        "days_range": 30,
    }

    with (
        patch(
            "SKILLS.kalodata_researcher.service.get_cached",
            new_callable=AsyncMock,
            return_value=cached_data,
        ),
        patch(
            "SKILLS.kalodata_researcher.service.search_products",
            new_callable=AsyncMock,
        ) as mock_search,
    ):
        result = await skill.run(inp, ctx)

    assert result.success is True
    assert result.cached is True
    assert result.data is not None
    assert result.data.products[0].product_id == "cached-1"
    # search_products must NOT have been called
    mock_search.assert_not_awaited()


@pytest.mark.asyncio
async def test_upstream_error_propagates():
    """When search_products raises UpstreamError it propagates through run()."""
    from core.errors import UpstreamError

    skill = KalodataResearcherSkill()
    inp = _make_input()
    ctx = _make_ctx()

    with (
        patch(
            "SKILLS.kalodata_researcher.service.get_cached", new_callable=AsyncMock, return_value=None
        ),
        patch(
            "SKILLS.kalodata_researcher.service.search_products",
            new_callable=AsyncMock,
            side_effect=UpstreamError(
                message="boom", skill="kalodata-researcher", code="UPSTREAM_ERROR"
            ),
        ),
    ):
        with pytest.raises(UpstreamError) as exc_info:
            await skill.run(inp, ctx)

    assert exc_info.value.code == "UPSTREAM_ERROR"
