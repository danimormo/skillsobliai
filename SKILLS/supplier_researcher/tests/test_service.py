"""Tests for the SupplierResearcherSkill service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.skill_interface import SkillContext
from core.errors import InvalidParamsError
from SKILLS.supplier_researcher.schemas import SupplierResearchInput
from SKILLS.supplier_researcher.service import SupplierResearcherSkill


def _make_ctx(user_id: str = "test_user") -> SkillContext:
    return SkillContext(user_id=user_id)


def _sample_aliexpress_result() -> list[dict]:
    return [
        {
            "source": "aliexpress",
            "product_id": "ali_001",
            "title": "Wireless Earbuds V5.3",
            "cost_usd": 4.50,
            "shipping_cost_usd": 1.20,
            "shipping_days_min": 15,
            "shipping_days_max": 30,
            "moq": 1,
            "supplier_rating": 4.7,
            "image_urls": ["https://img.example.com/ali1.jpg"],
            "product_url": "https://aliexpress.com/item/ali_001",
            "in_stock": True,
        }
    ]


def _sample_cj_result() -> list[dict]:
    return [
        {
            "source": "cj",
            "product_id": "cj_001",
            "title": "Bluetooth Earbuds Pro",
            "cost_usd": 5.80,
            "shipping_cost_usd": 0.00,
            "shipping_days_min": 7,
            "shipping_days_max": 15,
            "moq": 1,
            "supplier_rating": 4.9,
            "image_urls": ["https://img.example.com/cj1.jpg"],
            "product_url": "https://cjdropshipping.com/product/cj_001",
            "in_stock": True,
        }
    ]


def _sample_spocket_result() -> list[dict]:
    return [
        {
            "source": "spocket",
            "product_id": "sp_001",
            "title": "Premium Wireless Earbuds",
            "cost_usd": 8.00,
            "shipping_cost_usd": 2.50,
            "shipping_days_min": 3,
            "shipping_days_max": 7,
            "moq": 1,
            "supplier_rating": 4.5,
            "image_urls": ["https://img.example.com/sp1.jpg"],
            "product_url": "https://spocket.co/product/sp_001",
            "in_stock": True,
        }
    ]


@pytest.mark.asyncio
@patch("SKILLS.supplier_researcher.service.get_supabase")
@patch("SKILLS.supplier_researcher.service.cache")
@patch("SKILLS.supplier_researcher.service.api_client")
async def test_run_all_sources_parallel(mock_api, mock_cache, mock_supabase):
    """Test that all three sources are queried and results are aggregated."""
    mock_cache.get_cached = AsyncMock(return_value=None)
    mock_cache.set_cached = AsyncMock()
    mock_api.search_aliexpress = AsyncMock(return_value=_sample_aliexpress_result())
    mock_api.search_cj = AsyncMock(return_value=_sample_cj_result())
    mock_api.search_spocket = AsyncMock(return_value=_sample_spocket_result())

    sb_mock = MagicMock()
    sb_mock.table.return_value.insert.return_value.execute.return_value = None
    mock_supabase.return_value = sb_mock

    skill = SupplierResearcherSkill()
    input_data = SupplierResearchInput(
        product_name="wireless earbuds",
        target_price_usd=29.99,
        sources=["aliexpress", "cj", "spocket"],
    )
    ctx = _make_ctx()

    result = await skill.run(input_data, ctx)

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert result.data.total_found == 3
    assert len(result.data.products) == 3

    # Verify all sources were called
    mock_api.search_aliexpress.assert_awaited_once()
    mock_api.search_cj.assert_awaited_once()
    mock_api.search_spocket.assert_awaited_once()

    # Verify best picks
    assert result.data.best_price is not None
    assert result.data.best_price.product_id == "ali_001"  # 4.50 + 1.20 = 5.70 is lowest
    assert result.data.fastest_shipping is not None
    assert result.data.fastest_shipping.product_id == "sp_001"  # 3 days is fastest
    assert result.data.best_margin is not None

    # Verify margin calculation
    for p in result.data.products:
        assert p.margin_at_3x is not None


@pytest.mark.asyncio
@patch("SKILLS.supplier_researcher.service.get_supabase")
@patch("SKILLS.supplier_researcher.service.cache")
@patch("SKILLS.supplier_researcher.service.api_client")
async def test_run_returns_cached_result(mock_api, mock_cache, mock_supabase):
    """Test that cached results are returned without hitting APIs."""
    cached_output = {
        "total_found": 1,
        "products": [
            {
                "source": "aliexpress",
                "product_id": "ali_cached",
                "title": "Cached Product",
                "cost_usd": 3.00,
                "shipping_cost_usd": 1.00,
                "shipping_days_min": 10,
                "shipping_days_max": 20,
                "moq": 1,
                "supplier_rating": 4.0,
                "image_urls": [],
                "product_url": "https://aliexpress.com/item/ali_cached",
                "margin_at_3x": None,
                "in_stock": True,
            }
        ],
        "best_price": None,
        "best_margin": None,
        "fastest_shipping": None,
    }
    mock_cache.get_cached = AsyncMock(return_value=cached_output)

    skill = SupplierResearcherSkill()
    input_data = SupplierResearchInput(product_name="cached item")
    ctx = _make_ctx()

    result = await skill.run(input_data, ctx)

    assert result.success is True
    assert result.cached is True
    assert result.data is not None
    assert result.data.total_found == 1
    assert result.data.products[0].product_id == "ali_cached"

    # API should NOT be called
    mock_api.search_aliexpress.assert_not_awaited()
    mock_api.search_cj.assert_not_awaited()
    mock_api.search_spocket.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_empty_product_name():
    """Test that an empty product_name raises InvalidParamsError."""
    skill = SupplierResearcherSkill()
    input_data = SupplierResearchInput(product_name="  ")

    with pytest.raises(InvalidParamsError, match="product_name must not be empty"):
        skill.validate(input_data)
