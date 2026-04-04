from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.supplier_checker.schemas import SupplierCheckerInput
from SKILLS.supplier_checker.service import (
    SupplierCheckerSkill,
    calculate_margin,
)
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return SupplierCheckerSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return SupplierCheckerInput(
        product_title="LED posture corrector",
        sale_price=39.99,
        supplier_cost=8.50,
        shipping_cost=4.0,
        daily_budget_usd=30.0,
        daily_orders_estimate=3.0,
    )


def test_calculate_margin_exact():
    """Verify the exact margin formula from the spec."""
    result = calculate_margin(
        sale_price=39.99,
        supplier_cost=8.50,
        shipping_cost=4.0,
        daily_budget=30.0,
        daily_orders=3.0,
    )
    # cost_per_order_ads = 30 / 3 = 10.0
    # shopify_fee = 39.99 * 0.029 + 0.30 = 1.45971
    # refund_buffer = 39.99 * 0.03 = 1.1997
    # total_cost = 8.50 + 4.0 + 10.0 + 1.45971 + 1.1997 = 25.15941
    # net_margin_usd = 39.99 - 25.15941 = 14.83059
    # net_margin_pct = 14.83059 / 39.99 = 0.37086...
    assert result["breakdown"]["supplier"] == 8.50
    assert result["breakdown"]["shipping"] == 4.0
    assert result["breakdown"]["ads_per_order"] == 10.0
    assert abs(result["net_margin_pct"] - 0.3709) < 0.01
    assert abs(result["net_margin_usd"] - 14.83) < 0.1


@pytest.mark.asyncio
async def test_run_with_provided_cost(skill, ctx, sample_input):
    """When supplier_cost is provided, skip AliExpress search and calculate margin."""
    with (
        patch(
            "SKILLS.supplier_checker.cache.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "SKILLS.supplier_checker.cache.set_cached",
            new_callable=AsyncMock,
        ),
    ):
        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert result.data.best_supplier_source == "user_provided"
    assert result.data.best_supplier_cost == 8.50
    assert result.data.is_viable is True
    assert result.data.flag == "green"


@pytest.mark.asyncio
async def test_run_cache_hit(skill, ctx, sample_input):
    """When cache contains data, no API calls are made."""
    cached_output = {
        "product_title": "LED posture corrector",
        "sale_price": 39.99,
        "best_supplier_cost": 8.50,
        "best_supplier_source": "user_provided",
        "net_margin_pct": 0.37,
        "net_margin_usd": 14.83,
        "is_viable": True,
        "flag": "green",
        "breakdown": {"supplier": 8.50, "shipping": 4.0, "ads_per_order": 10.0,
                       "shopify_fee": 1.46, "refund_buffer": 1.20},
        "recommendation": "Strong margin.",
        "alternative_suppliers": [],
    }

    with (
        patch(
            "SKILLS.supplier_checker.cache.get_cached",
            new_callable=AsyncMock,
            return_value=cached_output,
        ),
        patch(
            "SKILLS.supplier_checker.api_client.search_aliexpress",
            new_callable=AsyncMock,
        ) as mock_search,
    ):
        result = await skill.run(sample_input, ctx)

    mock_search.assert_not_awaited()
    assert result.success is True
    assert result.cached is True
    assert result.data.best_supplier_cost == 8.50
