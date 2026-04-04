from unittest.mock import MagicMock, patch

import pytest

from SKILLS.C_product_scorer.schemas import ProductScorerInput
from SKILLS.C_product_scorer.service import (
    ProductScorerSkill,
    apply_gender_filter,
    score_product,
)
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return ProductScorerSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


def _make_item(**overrides) -> dict:
    base = {
        "item_id": "p1",
        "title": "Summer Dress",
        "image_url": "https://example.com/dress.jpg",
        "product_url": "https://shop.com/dress",
        "price": 29.99,
        "currency": "EUR",
        "country": "DE",
        "source": "tiktok_shop",
        "is_fashion": True,
        "confidence": 0.95,
        "category": "dresses",
        "gender": "woman",
        "eu_market_fit": True,
        "sold_count": 50000,
        "rating": 4.8,
        "trust_label": "best_seller",
        "creator_video": {"stats": {"plays": 15_000_000}},
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_run_happy_path(skill, ctx):
    """Products are scored, filtered, and sorted correctly."""
    items = [
        _make_item(item_id="p1", confidence=0.95, sold_count=50000, rating=4.8),
        _make_item(item_id="p2", confidence=0.80, sold_count=1000, rating=3.0, trust_label=None,
                   creator_video=None, eu_market_fit=False),
    ]
    inp = ProductScorerInput(items=items, params={"gender": "woman"}, n_results=10)

    with patch("SKILLS.C_product_scorer.service.get_supabase") as mock_sb:
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(inp, ctx)

    assert result.success is True
    assert result.data is not None
    assert result.data.total_input == 2
    assert result.data.total_returned == 2
    # First item should have higher score
    assert result.data.products[0].score >= result.data.products[1].score
    assert result.data.products[0].item_id == "p1"


@pytest.mark.asyncio
async def test_gender_filter_removes_items(skill, ctx):
    """Gender filter removes items of opposite gender."""
    items = [
        _make_item(item_id="p1", gender="woman"),
        _make_item(item_id="p2", gender="man"),
        _make_item(item_id="p3", gender="unisex"),
    ]
    inp = ProductScorerInput(items=items, params={"gender": "woman"}, n_results=10)

    with patch("SKILLS.C_product_scorer.service.get_supabase") as mock_sb:
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(inp, ctx)

    assert result.data.gender_filter_applied is True
    # "man" item should be excluded
    returned_ids = [p.item_id for p in result.data.products]
    assert "p2" not in returned_ids
    assert "p1" in returned_ids
    assert "p3" in returned_ids


@pytest.mark.asyncio
async def test_confidence_filter(skill, ctx):
    """Items with confidence < 0.7 or is_fashion=False are excluded."""
    items = [
        _make_item(item_id="p1", confidence=0.95, is_fashion=True),
        _make_item(item_id="p2", confidence=0.5, is_fashion=True),
        _make_item(item_id="p3", confidence=0.9, is_fashion=False),
    ]
    inp = ProductScorerInput(items=items, params={}, n_results=10)

    with patch("SKILLS.C_product_scorer.service.get_supabase") as mock_sb:
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(inp, ctx)

    assert result.data.total_after_filter == 1
    assert result.data.products[0].item_id == "p1"


def test_score_product_tiktok_shop():
    """Verify scoring formula for tiktok_shop source."""
    item = _make_item(
        confidence=0.95,
        source="tiktok_shop",
        sold_count=50000,
        rating=4.8,
        trust_label="best_seller",
        eu_market_fit=True,
        gender="woman",
        creator_video={"stats": {"plays": 15_000_000}},
    )
    params = {"gender": "woman"}
    s = score_product(item, params)

    # confidence: int(0.95*40) = 38
    # tiktok: min(50000/10000,20)=5 + (4.8/5)*10=9.6 + 5(best_seller) = int(19.6) = 19
    # eu_market_fit: 5
    # gender_match: 10
    # creator_virality: 15 (plays > 10M)
    # total: 38 + 19 + 5 + 10 + 15 = 87
    assert s == 87


def test_score_product_meta_ads():
    """Verify scoring formula for meta_ads source."""
    item = {
        "confidence": 0.8,
        "source": "meta_ads",
        "days_running": 45,
        "eu_market_fit": False,
        "gender": "unisex",
    }
    params = {"gender": "woman"}
    s = score_product(item, params)

    # confidence: int(0.8*40) = 32
    # meta_ads: min(50, 45*1.5)=min(50,67.5)=50 + 10(days>30) + 0(days<=60) = 60 -> min(60,35) = 35
    # eu_market_fit: 0
    # gender_match: 10 (unisex matches woman)
    # creator_virality: 0
    # total: 32 + 35 + 0 + 10 + 0 = 77
    assert s == 77


def test_apply_gender_filter():
    """Gender filter correctly excludes opposite gender."""
    items = [
        {"gender": "woman"},
        {"gender": "man"},
        {"gender": "unisex"},
    ]
    result = apply_gender_filter(items, "woman")
    assert len(result) == 2
    assert all(i["gender"] != "man" for i in result)

    result = apply_gender_filter(items, "man")
    assert len(result) == 2
    assert all(i["gender"] != "woman" for i in result)

    result = apply_gender_filter(items, None)
    assert len(result) == 3
