from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.B_vision_classifier.router import router
from SKILLS.B_vision_classifier.schemas import ClassifiedItem, VisionClassifierOutput
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[VisionClassifierOutput]:
    return SkillResult(
        success=True,
        data=VisionClassifierOutput(
            total_processed=1,
            total_fashion=1,
            total_non_fashion=0,
            total_errors=0,
            items=[
                ClassifiedItem(
                    item_id="p1",
                    image_url="https://example.com/dress.jpg",
                    is_fashion=True,
                    confidence=0.9,
                    category="dresses",
                    subcategory="summer_dress",
                    target_gender="women",
                    gender="woman",
                    price_tier="mid",
                    style_tags=["casual"],
                    reasoning="A dress",
                    eu_market_fit=True,
                    classification_error=None,
                )
            ],
        ),
        cached=False,
        execution_ms=500,
    )


def test_run_success():
    """POST /vision-classifier/run returns 200 with valid input."""
    with patch(
        "SKILLS.B_vision_classifier.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json={
                "items": [
                    {"item_id": "p1", "image_url": "https://example.com/dress.jpg", "title": "Dress"}
                ],
                "batch_size": 5,
            },
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["total_fashion"] == 1


def test_run_missing_auth():
    """POST without Authorization header returns 422."""
    response = client.post(
        "/run",
        json={
            "items": [{"item_id": "p1", "image_url": "https://example.com/img.jpg"}],
        },
    )
    assert response.status_code == 422
