from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.roas_monitor.schemas import ROASMonitorInput
from SKILLS.roas_monitor.service import ROASMonitorSkill
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return ROASMonitorSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return ROASMonitorInput(force_refresh=False)


def _mock_supabase(campaigns=None, meta_token="tok_abc"):
    """Build a mock Supabase client with campaigns and integration data."""
    mock_sb = MagicMock()

    # campaigns query
    campaigns_resp = MagicMock()
    campaigns_resp.data = campaigns or []
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = campaigns_resp

    # user_integrations query (single)
    integration_resp = MagicMock()
    integration_resp.data = {"access_token": meta_token} if meta_token else None
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = integration_resp

    # insert snapshot
    mock_sb.table.return_value.insert.return_value.execute.return_value = None

    return mock_sb


@pytest.mark.asyncio
async def test_run_no_campaigns(skill, ctx, sample_input):
    """When user has no active campaigns, return empty results."""
    mock_sb = _mock_supabase(campaigns=[])

    with patch("SKILLS.roas_monitor.service.get_supabase", return_value=mock_sb):
        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.data.campaigns_checked == 0
    assert result.data.results == []


@pytest.mark.asyncio
async def test_run_happy_path(skill, ctx, sample_input):
    """Successful fetch returns ROAS data and saves snapshot."""
    campaigns = [
        {
            "id": "camp-db-1",
            "meta_campaign_id": "120001",
            "name": "Summer Sale",
            "ad_account_id": "99001",
        }
    ]
    mock_sb = _mock_supabase(campaigns=campaigns, meta_token="tok_abc")

    insights_data = {
        "roas": 3.5,
        "spend": 100.0,
        "revenue": 350.0,
        "impressions": 5000,
        "clicks": 200,
        "conversions": 15,
    }

    with (
        patch("SKILLS.roas_monitor.service.get_supabase", return_value=mock_sb),
        patch.object(
            skill._insights_client,
            "get_campaign_insights",
            new_callable=AsyncMock,
            return_value=insights_data,
        ),
    ):
        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.data.campaigns_checked == 1
    assert result.data.snapshots_saved == 1
    assert len(result.data.results) == 1
    assert result.data.results[0].roas == 3.5
    assert result.data.results[0].spend_usd == 100.0


@pytest.mark.asyncio
async def test_run_insight_failure_skipped(skill, ctx, sample_input):
    """When insight fetch fails for a campaign, it is skipped gracefully."""
    campaigns = [
        {
            "id": "camp-db-1",
            "meta_campaign_id": "120001",
            "name": "Summer Sale",
            "ad_account_id": "99001",
        }
    ]
    mock_sb = _mock_supabase(campaigns=campaigns, meta_token="tok_abc")

    with (
        patch("SKILLS.roas_monitor.service.get_supabase", return_value=mock_sb),
        patch.object(
            skill._insights_client,
            "get_campaign_insights",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Meta API down"),
        ),
    ):
        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.data.campaigns_checked == 1
    assert result.data.snapshots_saved == 0
    assert result.data.results == []
