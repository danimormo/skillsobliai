from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.scale_kill_engine.schemas import ScaleKillInput
from SKILLS.scale_kill_engine.service import ScaleKillEngineSkill
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return ScaleKillEngineSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


def _mock_supabase(meta_token="tok_abc", daily_budget=100.0, meta_campaign_id="mc_1"):
    mock_sb = MagicMock()

    # user_integrations single
    integration_resp = MagicMock()
    integration_resp.data = {"access_token": meta_token}
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = integration_resp

    # campaigns single
    campaign_resp = MagicMock()
    campaign_resp.data = {
        "daily_budget_usd": daily_budget,
        "meta_campaign_id": meta_campaign_id,
    }
    mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = campaign_resp

    # update
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = None

    return mock_sb


@pytest.mark.asyncio
async def test_hold_action(skill, ctx):
    """When ROAS is within range, action is hold and nothing is executed."""
    inp = ScaleKillInput(
        campaign_db_id="camp-1",
        current_roas=1.8,
        current_spend_usd=50.0,
        roas_history=[{"roas": 1.7}, {"roas": 1.8}],
    )
    result = await skill.run(inp, ctx)

    assert result.success is True
    assert result.data.action == "hold"
    assert result.data.executed is False


@pytest.mark.asyncio
async def test_kill_action(skill, ctx):
    """Low ROAS with sufficient spend triggers kill."""
    inp = ScaleKillInput(
        campaign_db_id="camp-1",
        current_roas=0.5,
        current_spend_usd=50.0,
        roas_history=[{"roas": 0.4}, {"roas": 0.5}],
    )
    mock_sb = _mock_supabase()

    with (
        patch("SKILLS.scale_kill_engine.service.get_supabase", return_value=mock_sb),
        patch.object(
            skill._manus_client,
            "kill_campaign",
            new_callable=AsyncMock,
            return_value="task_kill_001",
        ),
    ):
        result = await skill.run(inp, ctx)

    assert result.data.action == "kill"
    assert result.data.executed is True
    assert result.data.manus_task_id == "task_kill_001"


@pytest.mark.asyncio
async def test_scale_action(skill, ctx):
    """ROAS above scale threshold for consecutive days triggers scale."""
    inp = ScaleKillInput(
        campaign_db_id="camp-1",
        current_roas=3.0,
        current_spend_usd=80.0,
        roas_history=[{"roas": 2.0}, {"roas": 3.1}, {"roas": 3.0}],
    )
    mock_sb = _mock_supabase(daily_budget=100.0)

    with (
        patch("SKILLS.scale_kill_engine.service.get_supabase", return_value=mock_sb),
        patch.object(
            skill._manus_client,
            "scale_budget",
            new_callable=AsyncMock,
            return_value="task_scale_001",
        ),
    ):
        result = await skill.run(inp, ctx)

    assert result.data.action == "scale"
    assert result.data.executed is True
    assert result.data.new_budget_usd == 120.0
    assert result.data.previous_budget_usd == 100.0
