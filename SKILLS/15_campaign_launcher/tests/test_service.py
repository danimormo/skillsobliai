from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.campaign_launcher.schemas import CampaignLauncherInput
from SKILLS.campaign_launcher.service import CampaignLauncherSkill
from core.errors import IntegrationNotConnectedError, InvalidParamsError
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return CampaignLauncherSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return CampaignLauncherInput(
        shop_domain="test-store.myshopify.com",
        campaign_name="Summer Sale IT",
        daily_budget_usd=20.0,
        target_countries=["IT"],
        pixel_id="px_123",
        ad_account_id="act_456",
        creative_image_urls=["https://cdn.example.com/img1.jpg"],
        ad_copy="Shop the best deals!",
        ad_headline="Summer Sale",
        destination_url="https://test-store.com/summer",
    )


def _mock_supabase_with_token(token: str | None = "meta-token-abc"):
    """Return a mock supabase client that returns a Meta token (or None)."""
    mock_sb = MagicMock()
    row_data = {"access_token": token} if token else None
    mock_result = MagicMock()
    mock_result.data = row_data
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_result
    # For the campaigns insert
    mock_sb.table.return_value.insert.return_value.execute.return_value = None
    return mock_sb


@pytest.mark.asyncio
async def test_run_happy_path(skill, ctx, sample_input):
    """Full launch flow returns campaign output."""
    mock_sb = _mock_supabase_with_token("meta-token-abc")

    with (
        patch(
            "SKILLS.campaign_launcher.service.get_supabase",
            return_value=mock_sb,
        ),
        patch.object(
            skill.manus,
            "submit_task",
            new_callable=AsyncMock,
            return_value="task_001",
        ),
        patch.object(
            skill.manus,
            "poll_task",
            new_callable=AsyncMock,
            return_value={
                "status": "completed",
                "campaign_id": "camp_111",
                "adset_id": "adset_222",
                "ad_id": "ad_333",
            },
        ),
        patch.object(
            skill.verifier,
            "verify_campaign",
            new_callable=AsyncMock,
            return_value={"id": "camp_111", "status": "ACTIVE"},
        ),
    ):
        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert result.data.meta_campaign_id == "camp_111"
    assert result.data.meta_adset_id == "adset_222"
    assert result.data.meta_ad_id == "ad_333"
    assert result.data.manus_task_id == "task_001"
    assert result.data.status == "ACTIVE"


@pytest.mark.asyncio
async def test_run_integration_not_connected(skill, ctx, sample_input):
    """Raises IntegrationNotConnectedError when Meta token is missing."""
    mock_sb = _mock_supabase_with_token(None)

    with (
        patch(
            "SKILLS.campaign_launcher.service.get_supabase",
            return_value=mock_sb,
        ),
        pytest.raises(IntegrationNotConnectedError),
    ):
        await skill.run(sample_input, ctx)


@pytest.mark.asyncio
async def test_validate_no_images(skill, ctx):
    """Raises InvalidParamsError when creative_image_urls is empty."""
    bad_input = CampaignLauncherInput(
        shop_domain="store.myshopify.com",
        campaign_name="Bad Campaign",
        daily_budget_usd=20.0,
        pixel_id="px_1",
        ad_account_id="act_1",
        creative_image_urls=[],
        ad_copy="copy",
        ad_headline="headline",
        destination_url="https://example.com",
    )
    with pytest.raises(InvalidParamsError):
        skill.validate(bad_input)
