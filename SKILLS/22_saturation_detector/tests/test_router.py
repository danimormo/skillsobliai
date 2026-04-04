from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.saturation_detector.router import router
from SKILLS.saturation_detector.schemas import SaturationDetectorOutput
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[SaturationDetectorOutput]:
    return SkillResult(
        success=True,
        data=SaturationDetectorOutput(
            product_title="LED posture corrector",
            stores_found=3,
            stores_sampled=50,
            saturation_index=0.06,
            saturation_level="medium",
            flag="yellow",
            recommendation="Medium saturation.",
            found_in_stores=["store1.com", "store2.com", "store3.com"],
        ),
        cached=False,
        execution_ms=1200,
    )


def test_run_success():
    """POST /saturation-detector/run returns 200 with valid input."""
    with patch(
        "SKILLS.saturation_detector.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json={
                "product_title": "LED posture corrector",
                "product_keywords": ["posture belt"],
                "sample_size": 50,
            },
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["stores_found"] == 3


def test_run_missing_auth():
    """POST without Authorization header returns 422 (missing required header)."""
    response = client.post(
        "/run",
        json={
            "product_title": "LED posture corrector",
        },
    )
    assert response.status_code == 422
