from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.theme_configurator.schemas import ThemeConfiguratorInput
from SKILLS.theme_configurator.service import ThemeConfiguratorSkill
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return ThemeConfiguratorSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return ThemeConfiguratorInput(
        shop_domain="test-store.myshopify.com",
        theme_preset="shrine",
        primary_color="#111111",
        secondary_color="#eeeeee",
        accent_color="#ff0000",
        enable_sticky_cart=True,
    )


def _mock_supabase_with_creds():
    """Return a mock supabase that has Shopify credentials."""
    mock_sb = MagicMock()
    # user_integrations query
    mock_creds = MagicMock()
    mock_creds.data = [{"access_token": "shpat_test123", "metadata": {}}]

    mock_select = MagicMock()
    mock_select.eq.return_value = mock_select
    mock_select.limit.return_value = mock_select
    mock_select.execute.return_value = mock_creds

    # research_results insert
    mock_insert = MagicMock()
    mock_insert.execute.return_value = None

    def table_router(name):
        t = MagicMock()
        if name == "user_integrations":
            t.select.return_value = mock_select
        elif name == "research_results":
            t.insert.return_value = mock_insert
        return t

    mock_sb.table.side_effect = table_router
    return mock_sb


@pytest.mark.asyncio
async def test_run_happy_path(skill, ctx, sample_input):
    """Successful theme configuration returns modified settings list."""
    mock_themes = [
        {"id": 12345, "name": "Dawn", "role": "main"},
        {"id": 99999, "name": "Old Theme", "role": "unpublished"},
    ]

    with (
        patch(
            "SKILLS.theme_configurator.service.get_supabase",
            return_value=_mock_supabase_with_creds(),
        ),
        patch(
            "SKILLS.theme_configurator.api_client.ShopifyThemeClient.get_themes",
            new_callable=AsyncMock,
            return_value=mock_themes,
        ),
        patch(
            "SKILLS.theme_configurator.api_client.ShopifyThemeClient.update_theme_settings",
            new_callable=AsyncMock,
            return_value={"key": "config/settings_data.json"},
        ),
    ):
        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert result.data.theme_id == "12345"
    assert result.data.theme_name == "Dawn"
    assert "primary_color" in result.data.settings_modified
    assert "accent_color" in result.data.settings_modified
    assert result.data.success is True


@pytest.mark.asyncio
async def test_run_no_integration(skill, ctx, sample_input):
    """Missing Shopify integration raises IntegrationNotConnectedError."""
    mock_sb = MagicMock()
    mock_creds = MagicMock()
    mock_creds.data = []

    mock_select = MagicMock()
    mock_select.eq.return_value = mock_select
    mock_select.limit.return_value = mock_select
    mock_select.execute.return_value = mock_creds
    mock_sb.table.return_value.select.return_value = mock_select

    from core.errors import IntegrationNotConnectedError

    with (
        patch(
            "SKILLS.theme_configurator.service.get_supabase",
            return_value=mock_sb,
        ),
        pytest.raises(IntegrationNotConnectedError),
    ):
        await skill.run(sample_input, ctx)


@pytest.mark.asyncio
async def test_validate_empty_domain(skill):
    """Empty shop_domain raises InvalidParamsError."""
    bad_input = ThemeConfiguratorInput(shop_domain="   ")

    from core.errors import InvalidParamsError

    with pytest.raises(InvalidParamsError):
        skill.validate(bad_input)
