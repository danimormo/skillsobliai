from unittest.mock import MagicMock, patch

import pytest

from SKILLS.stripe_billing.schemas import (
    CancelInput,
    ChangePlanInput,
    CreateSubscriptionInput,
)
from SKILLS.stripe_billing.service import (
    handle_cancel,
    handle_change_plan,
    handle_create_subscription,
)


def _mock_supabase():
    """Create a mock Supabase client with chained query methods."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_sb.table.return_value = mock_table
    return mock_sb, mock_table


@pytest.mark.asyncio
async def test_create_subscription_success():
    """Creating a subscription persists to DB and returns subscription details."""
    mock_sb, mock_table = _mock_supabase()

    # First call to select (check existing customer) returns no data
    mock_table.execute.return_value = MagicMock(data=[])

    mock_subscription = MagicMock()
    mock_subscription.id = "sub_test123"
    mock_subscription.status = "active"
    mock_subscription.cancel_at_period_end = False
    mock_subscription.current_period_start = 1700000000
    mock_subscription.current_period_end = 1702592000
    mock_subscription.get.return_value = None
    mock_subscription.__getitem__ = lambda self, key: {
        "latest_invoice": None,
    }.get(key)

    with (
        patch("SKILLS.stripe_billing.service.get_supabase", return_value=mock_sb),
        patch("SKILLS.stripe_billing.service.create_customer") as mock_create_cust,
        patch("SKILLS.stripe_billing.service.stripe_create_sub", return_value=mock_subscription),
    ):
        mock_create_cust.return_value = MagicMock(id="cus_test123")

        input_data = CreateSubscriptionInput(
            plan="growth",
            payment_method_id="pm_test123",
        )
        result = await handle_create_subscription(input_data, user_id="test-user-001")

    assert result.subscription_id == "sub_test123"
    assert result.status == "active"
    assert result.plan == "growth"


@pytest.mark.asyncio
async def test_cancel_subscription_success():
    """Cancelling sets cancel_at_period_end and updates DB."""
    mock_sb, mock_table = _mock_supabase()
    mock_table.execute.return_value = MagicMock(
        data=[{"stripe_subscription_id": "sub_test123", "plan": "growth"}]
    )

    mock_subscription = MagicMock()
    mock_subscription.status = "active"

    with (
        patch("SKILLS.stripe_billing.service.get_supabase", return_value=mock_sb),
        patch("SKILLS.stripe_billing.service.stripe_cancel", return_value=mock_subscription),
    ):
        result = await handle_cancel(CancelInput(), user_id="test-user-001")

    assert result.subscription_id == "sub_test123"
    assert result.plan == "growth"


@pytest.mark.asyncio
async def test_change_plan_success():
    """Changing plan modifies subscription and updates DB."""
    mock_sb, mock_table = _mock_supabase()
    mock_table.execute.return_value = MagicMock(
        data=[{"stripe_subscription_id": "sub_test123"}]
    )

    mock_subscription = MagicMock()
    mock_subscription.status = "active"

    with (
        patch("SKILLS.stripe_billing.service.get_supabase", return_value=mock_sb),
        patch("SKILLS.stripe_billing.service.stripe_change_plan", return_value=mock_subscription),
    ):
        result = await handle_change_plan(
            ChangePlanInput(new_plan="agency"), user_id="test-user-001"
        )

    assert result.subscription_id == "sub_test123"
    assert result.plan == "agency"
