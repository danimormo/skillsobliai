from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.image_creator.router import router
from SKILLS.image_creator.schemas import GeneratedImage, ImageCreatorOutput
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[ImageCreatorOutput]:
    return SkillResult(
        success=True,
        data=ImageCreatorOutput(
            job_id="job-001",
            images=[
                GeneratedImage(
                    storage_path="generated-images/user/job-001_0.png",
                    signed_url="https://storage.example.com/signed",
                    prompt_used="test prompt",
                    fal_seed=42,
                    width=1024,
                    height=1024,
                    variant="product_shot",
                )
            ],
            credits_used=1,
            credits_remaining=99,
        ),
        cached=False,
        execution_ms=1200,
    )


def test_run_success():
    """POST /run returns 200 with valid input."""
    with patch(
        "SKILLS.image_creator.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json={
                "product_title": "Organic Matcha Powder",
                "variant": "product_shot",
                "num_images": 1,
                "image_size": "square_hd",
            },
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]["images"]) == 1
    assert body["data"]["credits_used"] == 1


def test_run_missing_auth():
    """POST without Authorization header returns 422."""
    response = client.post(
        "/run",
        json={
            "product_title": "Test Product",
            "variant": "product_shot",
        },
    )
    assert response.status_code == 422
