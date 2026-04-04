from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.smart_scorer.router import router
from SKILLS.smart_scorer.schemas import SmartScorerOutput
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[SmartScorerOutput]:
    return SkillResult(
        success=True,
        data=SmartScorerOutput(
            product_title="Test Product",
            score=72,
            tier="A",
            breakdown={
                "trend_momentum": 20,
                "multi_platform": 14,
                "saturation_inverse": 18,
                "margin": 12,
                "engagement": 10,
            },
            recommendation="Good opportunity. Test with moderate budget and monitor closely.",
        ),
        cached=False,
        execution_ms=5,
    )


def test_run_success():
    """POST /run returns 200 with valid input."""
    with patch(
        "SKILLS.smart_scorer.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json={
                "product_title": "Test Product",
                "total_ads": 50,
                "active_ads": 40,
                "found_on_meta": True,
                "found_on_tiktok": True,
            },
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["tier"] == "A"
    assert body["data"]["score"] == 72


def test_run_missing_auth():
    """POST without Authorization header returns 422."""
    response = client.post(
        "/run",
        json={"product_title": "Test Product"},
    )
    assert response.status_code == 422
