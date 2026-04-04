from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.creative_ideator.router import router
from SKILLS.creative_ideator.schemas import CreativeAngle, CreativeIdeatorOutput
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[CreativeIdeatorOutput]:
    return SkillResult(
        success=True,
        data=CreativeIdeatorOutput(
            product_title="Test Product",
            angles=[
                CreativeAngle(
                    name="Test Angle",
                    hook="Test hook",
                    script_30s="Test script",
                    format="UGC",
                    visual_refs=["ref1"],
                    target_emotion="curiosity",
                    estimated_ctr_tier="high",
                )
            ],
            recommended_angle="Test Angle",
            platform="meta",
        ),
        cached=False,
        execution_ms=150,
    )


def test_run_success():
    """POST /creative-ideator/run returns 200 with valid input."""
    with patch(
        "SKILLS.creative_ideator.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json={
                "product_title": "Test Product",
                "product_description": "A great product",
                "num_angles": 2,
                "platform": "meta",
            },
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["recommended_angle"] == "Test Angle"


def test_run_missing_auth():
    """POST without Authorization header returns 422."""
    response = client.post(
        "/run",
        json={
            "product_title": "Test Product",
            "product_description": "A great product",
        },
    )
    assert response.status_code == 422
