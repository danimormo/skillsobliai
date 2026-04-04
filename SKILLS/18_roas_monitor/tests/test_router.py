from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.roas_monitor.router import router
from SKILLS.roas_monitor.schemas import ROASMonitorOutput
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[ROASMonitorOutput]:
    return SkillResult(
        success=True,
        data=ROASMonitorOutput(
            campaigns_checked=0,
            snapshots_saved=0,
            actions_triggered=0,
            results=[],
            monitored_at="2026-04-04T00:00:00+00:00",
        ),
        cached=False,
        execution_ms=42,
    )


def test_run_success():
    """POST /run returns 200 with valid input."""
    with patch(
        "SKILLS.roas_monitor.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json={"force_refresh": False},
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["campaigns_checked"] == 0


def test_run_missing_auth():
    """POST without Authorization header returns 422."""
    response = client.post(
        "/run",
        json={"force_refresh": False},
    )
    assert response.status_code == 422
