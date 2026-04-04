from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.16_campaign_validator.schemas import CampaignValidatorInput
from SKILLS.16_campaign_validator.service import CampaignValidatorSkill
from core.errors import IntegrationNotConnectedError
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return CampaignValidatorSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return CampaignValidatorInput(
        ad_account_id="act_456",
        pixel_id="px_123",
        campaign_name="Summer Sale IT",
        daily_budget_usd=20.0,
        target_countries=["IT"],
        creative_image_urls=["https://cdn.example.com/img1.jpg"],
        ad_copy="Shop the best deals!",
        ad_headline="Summer Sale",
        destination_url="https://test-store.com/summer",
        product_price=29.90,
        product_cost=8.0,
        shipping_cost=4.0,
    )


def _mock_supabase(token: str | None = "meta-token-abc"):
    mock_sb = MagicMock()
    row_data = {"access_token": token} if token else None
    mock_result = MagicMock()
    mock_result.data = row_data
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_result
    return mock_sb


@pytest.mark.asyncio
async def test_run_all_checks_pass(skill, ctx, sample_input):
    """All checks pass -> can_launch is True."""
    with (
        patch(
            "SKILLS.16_campaign_validator.service.get_supabase",
            return_value=_mock_supabase(),
        ),
        patch.object(
            skill.meta,
            "check_ad_account",
            new_callable=AsyncMock,
            return_value={"account_status": 1, "name": "Test Account"},
        ),
        patch.object(
            skill.meta,
            "check_pixel",
            new_callable=AsyncMock,
            return_value={"is_unavailable": False, "last_fired_time": "2026-04-01T00:00:00"},
        ),
        patch.object(
            skill.meta,
            "check_funding",
            new_callable=AsyncMock,
            return_value={"id": "funding_001"},
        ),
    ):
        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.data.can_launch is True
    assert len(result.data.checks) == 8
    blocking_checks = [c for c in result.data.checks if c.blocking]
    assert all(c.passed for c in blocking_checks)


@pytest.mark.asyncio
async def test_run_budget_too_low(skill, ctx, sample_input):
    """Low budget causes budget_check to fail -> can_launch is False."""
    sample_input.daily_budget_usd = 3.0

    with (
        patch(
            "SKILLS.16_campaign_validator.service.get_supabase",
            return_value=_mock_supabase(),
        ),
        patch.object(
            skill.meta,
            "check_ad_account",
            new_callable=AsyncMock,
            return_value={"account_status": 1},
        ),
        patch.object(
            skill.meta,
            "check_pixel",
            new_callable=AsyncMock,
            return_value={"is_unavailable": False, "last_fired_time": "2026-04-01T00:00:00"},
        ),
        patch.object(
            skill.meta,
            "check_funding",
            new_callable=AsyncMock,
            return_value={"id": "funding_001"},
        ),
    ):
        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.data.can_launch is False
    budget = next(c for c in result.data.checks if c.name == "budget_check")
    assert budget.passed is False


@pytest.mark.asyncio
async def test_run_integration_not_connected(skill, ctx, sample_input):
    """Missing Meta token raises IntegrationNotConnectedError."""
    with (
        patch(
            "SKILLS.16_campaign_validator.service.get_supabase",
            return_value=_mock_supabase(None),
        ),
        pytest.raises(IntegrationNotConnectedError),
    ):
        await skill.run(sample_input, ctx)
