from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.scale_kill_engine.router import router
from SKILLS.scale_kill_engine.schemas import ScaleKillOutput
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[ScaleKillOutput]:
    return SkillResult(
        success=True,
        data=ScaleKillOutput(
            campaign_db_id="camp-1",
            action="hold",
            reason="ROAS within acceptable range; no action needed.",
            previous_budget_usd=None,
            new_budget_usd=None,
            manus_task_id=None,
            executed=False,
        ),
        cached=False,
        execution_ms=10,
    )


def test_run_success():
    """POST /run returns 200 with valid input."""
    with patch(
        "SKILLS.scale_kill_engine.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json={
                "campaign_db_id": "camp-1",
                "current_roas": 1.8,
                "current_spend_usd": 50.0,
                "roas_history": [{"roas": 1.7}],
            },
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["action"] == "hold"


def test_run_missing_auth():
    """POST without Authorization header returns 422."""
    response = client.post(
        "/run",
        json={
            "campaign_db_id": "camp-1",
            "current_roas": 1.8,
            "current_spend_usd": 50.0,
            "roas_history": [],
        },
    )
    assert response.status_code == 422
