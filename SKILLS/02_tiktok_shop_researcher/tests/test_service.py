"""Tests for TikTok Shop Researcher service layer."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.tiktok_shop_researcher.schemas import TikTokShopInput, TikTokShopProduct
from SKILLS.tiktok_shop_researcher.service import (
    CURRENCY_MAP,
    TikTokShopResearcherSkill,
    filter_products,
    normalize_product,
    select_keywords,
)
from core.skill_interface import SkillContext


# ── Fixtures ────────────────────────────────────────────────────────────────


def _make_raw_product(
    product_id: str = "123",
    price: float = 29.99,
    sold: int = 5000,
    rating: float = 4.5,
    country: str = "US",
    seo_date: str | None = None,
    label: str = "",
) -> dict:
    if seo_date is None:
        seo_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    return {
        "id": product_id,
        "title": f"Test Product {product_id}",
        "image_url": "https://img.example.com/test.jpg",
        "product_url": "https://shop.tiktok.com/product/123",
        "price": price,
        "sold_count": sold,
        "rating": rating,
        "seo_url_updated_at": seo_date,
        "label": label,
    }


def _make_product(
    item_id: str = "tiktok_123",
    price: float = 29.99,
    sold_count: int = 5000,
    seo_date: str | None = None,
) -> TikTokShopProduct:
    if seo_date is None:
        seo_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    return TikTokShopProduct(
        item_id=item_id,
        title="Test Product",
        image_url="https://img.example.com/test.jpg",
        product_url="https://shop.tiktok.com/product/123",
        price=price,
        currency="USD",
        country="US",
        sold_count=sold_count,
        rating=4.5,
        velocity_signal="medium",
        new_arrival=False,
        seo_url_updated_at=seo_date,
    )


# ── Test 1: Happy path ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_happy_path():
    """Full run with mocked API returns products."""
    raw_products = [
        _make_raw_product(product_id=str(i), price=25.0, sold=6000)
        for i in range(5)
    ]

    skill = TikTokShopResearcherSkill()
    inp = TikTokShopInput(
        countries=["US"],
        keywords_by_country={"US": ["test keyword"]},
        n_results=3,
    )
    ctx = SkillContext(user_id="test-user-123")

    with (
        patch(
            "SKILLS.tiktok_shop_researcher.service.search_tiktok_shop",
            new_callable=AsyncMock,
            return_value=raw_products,
        ),
        patch(
            "SKILLS.tiktok_shop_researcher.service.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "SKILLS.tiktok_shop_researcher.service.set_cached",
            new_callable=AsyncMock,
        ),
        patch(
            "SKILLS.tiktok_shop_researcher.service.get_supabase",
        ) as mock_sb,
    ):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(inp, ctx)

    assert result.success is True
    assert result.data is not None
    assert result.data.total_fetched >= 1
    assert "US" in result.data.countries_searched
    assert len(result.data.products) <= 3


# ── Test 2: IE is silently skipped ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_ie_skipped():
    """IE country should be skipped and listed in countries_skipped."""
    skill = TikTokShopResearcherSkill()
    inp = TikTokShopInput(
        countries=["IE"],
        n_results=5,
    )
    ctx = SkillContext(user_id="test-user-ie")

    with (
        patch(
            "SKILLS.tiktok_shop_researcher.service.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "SKILLS.tiktok_shop_researcher.service.set_cached",
            new_callable=AsyncMock,
        ),
        patch(
            "SKILLS.tiktok_shop_researcher.service.get_supabase",
        ) as mock_sb,
    ):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(inp, ctx)

    assert result.success is True
    assert result.data is not None
    assert "IE" in result.data.countries_skipped
    assert "IE" not in result.data.countries_searched
    assert result.data.total_fetched == 0


# ── Test 3: Filter tier selection ───────────────────────────────────────────


def test_filter_tier_selection():
    """T1 is too strict, should fall through to a broader tier."""
    recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

    # Products that match T4 (price 1-150, sold>=500) but NOT T1/T2/T3
    products = [
        _make_product(item_id=f"tiktok_{i}", price=10.0, sold_count=600, seo_date=old)
        for i in range(5)
    ]

    filtered, tier = filter_products(products, 3)

    assert tier == 4
    assert len(filtered) >= 3

    # Products that match T1: revenue 89k-120k, fresh
    t1_products = [
        _make_product(
            item_id=f"tiktok_t1_{i}",
            price=20.0,
            sold_count=5000,  # revenue = 100k
            seo_date=recent,
        )
        for i in range(4)
    ]

    filtered_t1, tier_t1 = filter_products(t1_products, 3)
    assert tier_t1 == 1
    assert len(filtered_t1) >= 3
