from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.A_prompt_parser.router import router
from SKILLS.A_prompt_parser.schemas import ParsedParams, PromptParserOutput
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[PromptParserOutput]:
    return SkillResult(
        success=True,
        data=PromptParserOutput(
            parsed=ParsedParams(
                sources=["tiktok_shop"],
                countries=["US"],
                n_results=5,
                search_signal="winner",
                categories=[],
                keywords_by_country={},
            ),
            raw_response="{}",
            used_defaults=False,
        ),
        cached=False,
        execution_ms=100,
    )


def test_run_success():
    """POST /prompt-parser/run returns 200 with valid input."""
    with patch(
        "SKILLS.A_prompt_parser.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json={"prompt": "find trending dresses in europe"},
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["parsed"]["search_signal"] == "winner"


def test_run_missing_auth():
    """POST without Authorization header returns 422."""
    response = client.post(
        "/run",
        json={"prompt": "find trending dresses"},
    )
    assert response.status_code == 422
