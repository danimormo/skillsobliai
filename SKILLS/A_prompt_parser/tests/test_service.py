import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.A_prompt_parser.schemas import PromptParserInput
from SKILLS.A_prompt_parser.service import PromptParserSkill
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return PromptParserSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return PromptParserInput(prompt="Find trending women dresses in Europe under 50 euros")


def _make_parsed_response() -> dict:
    return {
        "sources": ["tiktok_shop"],
        "countries": ["GB", "DE", "FR", "IT", "ES", "IE"],
        "n_results": 5,
        "search_signal": "trending",
        "categories": ["dresses"],
        "gender": "woman",
        "price_max": 50.0,
        "price_min": None,
        "keywords_by_country": {
            "GB": ["summer dress", "women dress", "floral dress", "maxi dress", "casual dress", "party dress"],
            "DE": ["Sommerkleid", "Damenkleid", "Blumenkleid", "Maxikleid", "Freizeitkleid", "Partykleid"],
        },
    }


@pytest.mark.asyncio
async def test_run_happy_path(skill, ctx, sample_input):
    """Successful Claude parse returns structured params."""
    parsed = _make_parsed_response()
    with (
        patch(
            "SKILLS.A_prompt_parser.cache.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "SKILLS.A_prompt_parser.cache.set_cached",
            new_callable=AsyncMock,
        ),
        patch(
            "SKILLS.A_prompt_parser.api_client.parse_prompt",
            new_callable=AsyncMock,
            return_value=(parsed, json.dumps(parsed)),
        ),
        patch(
            "SKILLS.A_prompt_parser.service.get_supabase",
        ) as mock_sb,
    ):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert result.data.parsed.search_signal == "trending"
    assert result.data.parsed.gender == "woman"
    assert "GB" in result.data.parsed.countries
    assert result.data.used_defaults is False


@pytest.mark.asyncio
async def test_run_parse_failure_uses_defaults(skill, ctx, sample_input):
    """When Claude parse fails, defaults are applied."""
    with (
        patch(
            "SKILLS.A_prompt_parser.cache.get_cached",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "SKILLS.A_prompt_parser.cache.set_cached",
            new_callable=AsyncMock,
        ),
        patch(
            "SKILLS.A_prompt_parser.api_client.parse_prompt",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Claude unavailable"),
        ),
        patch(
            "SKILLS.A_prompt_parser.service.get_supabase",
        ) as mock_sb,
    ):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.data is not None
    assert result.data.used_defaults is True
    assert result.data.parsed.search_signal == "winner"
    assert result.data.parsed.n_results == 5


@pytest.mark.asyncio
async def test_run_cache_hit(skill, ctx, sample_input):
    """When cache contains data, Claude is never called."""
    cached_output = {
        "parsed": {
            "sources": ["tiktok_shop"],
            "countries": ["US"],
            "n_results": 10,
            "search_signal": "winner",
            "categories": [],
            "gender": None,
            "price_max": None,
            "price_min": None,
            "keywords_by_country": {},
        },
        "raw_response": "cached",
        "used_defaults": False,
    }

    with (
        patch(
            "SKILLS.A_prompt_parser.cache.get_cached",
            new_callable=AsyncMock,
            return_value=cached_output,
        ),
        patch(
            "SKILLS.A_prompt_parser.api_client.parse_prompt",
            new_callable=AsyncMock,
        ) as mock_parse,
    ):
        result = await skill.run(sample_input, ctx)

    mock_parse.assert_not_awaited()
    assert result.success is True
    assert result.cached is True
    assert result.data is not None
    assert result.data.parsed.n_results == 10
